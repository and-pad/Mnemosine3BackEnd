
from user_queries.views.tools import AuditManager
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated


from bson.objectid import ObjectId
from user_queries.driver_database.mongo import Mongo
import json
import os
import shutil

from user_queries.driver_database.mongo import Mongo
import string
from authentication.views import Permission
from PIL import Image
from django.conf import settings
import random
from user_queries.mongo_queries import (
    PIECES_ALL,

)
"""
    MODULES,
    pieceDetail,
    inventory_edit,
    research_edit,
"""

class InventoryEdit(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    # authentication_classes = [JWTAuthentication]
    # En este metodo/verbo get obtenemos los datos para visualizarlos al editar
    def get_inventory_module(self, mongo):
        return mongo.connect("modules").find_one({"name": "inventory"})

    def get_collection_json(self, mongo, collection_name, query=None, sort_field=None):
        """Obtiene documentos de una colección y los convierte a JSON."""
        collection = mongo.connect(collection_name)
        cursor = collection.find(query or {})
        if sort_field:
            cursor = cursor.sort(sort_field, 1)
        return json.loads(json.dumps(list(cursor), default=str))

    def get_catalog_elements(self, mongo, code):
        """Obtiene los elementos de un catálogo dado su código."""
        catalog = mongo.connect("catalogs").find_one({"code": code})
        if catalog:
            return self.get_collection_json(
                mongo, "catalog_elements", {"catalog_id": ObjectId(catalog["_id"])}
            )
        return []

    def get(self, request, _id):

        mongo = Mongo()

        inventoryChngapprov = mongo.connect("inventory_change_approvals")
        cursor_change = inventoryChngapprov.find_one(
            {"piece_id": ObjectId(_id), "approved_rejected": None}
        )

        if cursor_change is None:

            module = self.get_inventory_module(mongo)

            response_data = {
                "piece": self.get_collection_json(
                    mongo, "pieces_search", {"_id": ObjectId(_id)}
                )[0],
                "documents": self.get_collection_json(
                    mongo,
                    "documents",
                    {
                        "module_id": module["_id"],
                        "piece_id": ObjectId(_id),
                        "deleted_at": None,
                    },
                ),
                "pics": self.get_collection_json(
                    mongo,
                    "photographs",
                    {
                        "module_id": module["_id"],
                        "piece_id": ObjectId(_id),
                        "deleted_at": None,
                    },
                ),
                "genders": self.get_collection_json(
                    mongo, "genders", {"deleted_at": None}, "title"
                ),
                "subgenders": self.get_collection_json(
                    mongo, "subgenders", {"deleted_at": None}, "title"
                ),
                "type_object": self.get_catalog_elements(mongo, "object_type"),
                "dominant_material": self.get_catalog_elements(
                    mongo, "dominant_material"
                ),
            }

            return Response(response_data, status=status.HTTP_200_OK)
        else:
            # Necesito ver en los permisos ya esta la funcion si tiene el permiso necesario para acreditar
            # si puede aceptar los cambios, si no tiene ese permiso entonces debe poner un mensaje de que esta siendo editado y no se puede editar
            # hasta que se apruebe
            permissions = Permission()
            perm = permissions.get_permission(request.user)
            # Ya debe estar filtrado esto en el front end pero por refuerzo de seguridad
            # le buscamos en la base de datos

            if "editar_inventario" not in perm:
                return Response(
                    "You have not permission to approve",
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            exclusions = {
                "created_at",
                "updated_at",
                "created_by",
                "_id",
                "approved_rejected_by",
                "approved_rejected",
                "new_docs",
                "new_pics",
                "changed_pics_info",
                "changed_pics",
                "changed_docs_info",
                "changed_docs",
            }
            # Iteramos sobre cada clave-valor en `cursor_change`
            data_in_object = {"gender", "subgender"}

            data_to_approval = {
                key: (
                    {
                        "oldValue": item["oldValue"]["title"],
                        "newValue": item["newValue"]["title"],
                    }
                    if key in data_in_object
                    else item
                )
                for key, item in cursor_change.items()
                if key not in exclusions
            }

            data_to_approval["fields_changes"] = False
            for key, value in data_to_approval.items():
                if key != "piece_id" and key != "fields_changes":
                    print(key, value)
                    data_to_approval["fields_changes"] = True
                    break

            print(data_to_approval["fields_changes"])

            if "new_pics" in cursor_change:
                data_to_approval["new_pics"] = [
                    {
                        "file_name": pic["file_name"],
                        "description": pic["description"],
                        "photographer": pic["photographer"],
                        "photographed_at": pic["photographed_at"],
                        "size": pic["size"],
                        "mime_type": pic["mime_type"],
                    }
                    for pic in cursor_change["new_pics"]
                ]

            if "new_docs" in cursor_change:
                data_to_approval["new_docs"] = [
                    {
                        "file_name": doc["file_name"],
                        "title": doc["name"],
                        "size": doc["size"],
                        "mime_type": doc["mime_type"],
                    }
                    for doc in cursor_change["new_docs"]
                ]

            if "changed_pics" in cursor_change:

                old_data_pictures = {
                    pic["key"]: mongo.connect("photographs").find_one(
                        {"_id": ObjectId(pic["_id"])}
                    )
                    for pic in cursor_change["changed_pics"]
                    if mongo.connect("photographs").find_one(
                        {"_id": ObjectId(pic["_id"])}
                    )
                }

                data_to_approval["changed_pics"] = [
                    {
                        "key": pic["key"],
                        "old_file_name": old_data_pictures[pic["key"]]["file_name"],
                        "old_size": old_data_pictures[pic["key"]]["size"],
                        "old_mime_type": old_data_pictures[pic["key"]]["mime_type"],
                        "new_file_name": pic["file_name"],
                        "new_size": pic["size"],
                        "new_mime_type": pic["mime_type"],
                    }
                    for pic in cursor_change["changed_pics"]
                    if pic["key"] in old_data_pictures
                ]

            if "changed_pics_info" in cursor_change:

                data_picture = {
                    key: mongo.connect("photographs").find_one(
                        {"_id": ObjectId(value["_id"])}
                    )
                    for key, value in cursor_change["changed_pics_info"].items()
                }
                data_to_approval["changed_pics_info"] = [
                    {
                        **{k: v for k, v in value.items() if k != "_id"},
                        "file_name": data_picture[key]["file_name"],
                    }
                    for key, value in cursor_change["changed_pics_info"].items()
                ]

            if "changed_docs" in cursor_change:
                old_data_docs = {
                    doc["key"]: mongo.connect("documents").find_one(
                        {"_id": ObjectId(doc["_id"])}
                    )
                    for doc in cursor_change["changed_docs"]
                    if mongo.connect("documents").find_one(
                        {"_id": ObjectId(doc["_id"])}
                    )
                }
                data_to_approval["changed_docs"] = [
                    {
                        "key": doc["key"],
                        "old_file_name": old_data_docs[doc["key"]]["file_name"],
                        "old_size": old_data_docs[doc["key"]]["size"],
                        "old_mime_type": old_data_docs[doc["key"]]["mime_type"],
                        "new_file_name": doc["file_name"],
                        "new_size": doc["size"],
                        "new_mime_type": doc["mime_type"],
                    }
                    for doc in cursor_change["changed_docs"]
                    if doc["key"] in old_data_docs
                ]

            if "changed_docs_info" in cursor_change:
                data_doc = {
                    key: mongo.connect("documents").find_one(
                        {"_id": ObjectId(value["_id"])}
                    )
                    for key, value in cursor_change["changed_docs_info"].items()
                }
                data_to_approval["changed_docs_info"] = [
                    {
                        **{k: v for k, v in value.items() if k != "_id"},
                        "file_name": data_doc[key]["file_name"],
                    }
                    for key, value in cursor_change["changed_docs_info"].items()
                ]

            data_to_approval["changes"] = True
            json_to_approval = json.loads(json.dumps(data_to_approval, default=str))
            return Response(json_to_approval, status=status.HTTP_200_OK)

    def generate_random_file_name(self, original_filename, length=40):
        _, extension = os.path.splitext(original_filename)
        alphabet = string.ascii_letters + string.digits
        return "".join(random.choices(alphabet, k=length)) + extension

    # Este metodo lo utilizamos para crear la colección de revisión
    # ya que en este sistema las modificaciones pasan primero por una inspección
    # si se acepta la modificacion esta se recibira en put
    def get_json_data(self, request, key, default={}):
        return json.loads(request.data.get(key, default))

    def process_changes(self, request, key):
        changes = self.get_json_data(request, key)
        for key, value in changes.items():
            if "_id" in value and isinstance(value["_id"], str):
                value["_id"] = ObjectId(value["_id"])
        print(changes)
        return changes

    def save_temporary_files(self, file, filename):
        file_path = f"{settings.TEMPORARY_UPLOAD_DIRECTORY}{filename}"
        with open(file_path, "wb") as f:
            for chunk in file.chunks():
                f.write(chunk)

    def post(self, request, _id):
        """
        Aqui vienen los datos para actualizar el inventario
        primero pasan por una etapa de revision
        si se aprueba se actualiza el inventario eso en put
        si se rechaza se no se hacen los cambios
        los cambios se guardan en la base de datos en la colección inventory_changes_approval
        viene:
        changes, que son los inputs del inventario

        changes_pics_inputs, que son los inputs de las fotos
        changes_docs_inputs, que son los inputs de los documentos

        PicsNew, que son las fotos nuevas
        files[new_img_{x}], que son las fotos nuevas
        DocumentsNew, que son los documentos nuevos
        files[new_doc_{x}], que son los documentos nuevos

        changed_pics, que son los _id objectId de mongo de las fotos con combio
        files[changed_img_{x}], que son las fotos con cambios

        changed_docs, que son los _id objectId de mongo de los documentos con combio
        files[changed_doc_{x}], que son los documentos con cambios

        """
        # Get the user ID from the request
        user_id = request.user.id

        # Initialize the Mongo connection
        mongo = Mongo()

        # Connect to the inventory change approvals collection
        InventoryChanges = mongo.connect("inventory_change_approvals")

        # Get change data from the request
        changes = self.get_json_data(request, "changes")
        changes_pics_inputs = self.process_changes(
            request, "changes_pics_inputs"
        )  # pics
        changes_docs_inputs = self.process_changes(
            request, "changes_docs_inputs"
        )  # docs

        # Get changed documents and new documents from the request
        changed_docs = json.loads(request.data.get("changed_docs", "{}"))
        # print("changed_docs",changed_docs)
        docs_new = json.loads(request.data.get("DocumentsNew", "{}"))

        # Process new documents
        for index, doc in enumerate(docs_new):
            # Retrieve the file from the request
            if file := request.FILES.get(f"files[new_doc_{index}]"):
                # Generate a random file name
                filename = self.generate_random_file_name(file.name)
                # Add document details to changes
                changes.setdefault("new_docs", []).append(
                    {
                        "name": doc["name"],
                        "file_name": filename,
                        "size": doc["size"],
                        "mime_type": doc["mime_type"],
                    }
                )
                # Save the file temporarily
                self.save_temporary_files(file, filename)

        # Get changed pictures and new pictures from the request
        changed_pics = json.loads(request.data.get("changed_pics", "{}"))
        pics_new = json.loads(request.data.get("PicsNew", "{}"))

        # Process new pictures
        for index, pic in enumerate(pics_new):
            # Retrieve the file from the request
            if file := request.FILES.get(f"files[new_img_{index}]"):
                # Generate a random file name
                filename = self.generate_random_file_name(file.name)
                # Add picture details to changes
                changes.setdefault("new_pics", []).append(
                    {
                        "photographer": pic["photographer"],
                        "photographed_at": pic["photographed_at"],
                        "description": pic["description"],
                        "file_name": filename,
                        "size": pic["size"],
                        "mime_type": pic["mime_type"],
                    }
                )
                # Save the file temporarily
                self.save_temporary_files(file, filename)

        # List to store details of saved files
        saved_files_img = []
        # Process changed pictures
        for key, meta in changed_pics.items():
            # Retrieve the file from the request
            if file := request.FILES.get(f"files[changed_img_{key}]"):
                try:
                    # Generate a random file name
                    filename = self.generate_random_file_name(file.name)
                    # Save the file temporarily
                    self.save_temporary_files(file, filename)
                    # Append file details to saved_files
                    saved_files_img.append(
                        {
                            "key": key,
                            "_id": ObjectId(meta["_id"]),
                            "file_name": filename,
                            "size": file.size,
                            "mime_type": file.content_type,
                        }
                    )
                except Exception as e:
                    # Log any errors encountered during file saving
                    print(
                        f"Error: is not possible to create the file, check the file permissions or the path: {e}"
                    )
        saved_files_doc = []
        for key, meta in changed_docs.items():
            # Retrieve the file from the request
            if file := request.FILES.get(f"files[changed_doc_{key}]"):
                try:
                    # Generate a random file name
                    filename = self.generate_random_file_name(file.name)
                    # Save the file temporarily
                    self.save_temporary_files(file, filename)
                    # Append file details to saved_files
                    saved_files_doc.append(
                        {
                            "key": key,
                            "_id": ObjectId(meta["_id"]),
                            "file_name": filename,
                            "size": file.size,
                            "mime_type": file.content_type,
                        }
                    )
                except Exception as e:
                    # Log any errors encountered during file saving
                    print(
                        f"Error: is not possible to create the file, check the file permissions or the path: {e}"
                    )

        # Check if any of the data is a dictionary, indicating changes exist
        if any(
            isinstance(x, dict)
            for x in [
                changes,
                changes_pics_inputs,
                changed_pics,
                changes_docs_inputs,
                changed_docs,
            ]
        ):
            # Instantiate AuditManager for adding timestamps and approval info
            timestamps = AuditManager()
            combined_changes = {}

            # Combine changes into a single dictionary
            if changes:
                combined_changes = {**combined_changes, **changes}
            if changes_pics_inputs:
                combined_changes["changed_pics_info"] = changes_pics_inputs
            if changed_pics:
                combined_changes.setdefault("changed_pics", []).extend(saved_files_img)
            if changes_docs_inputs:
                combined_changes["changed_docs_info"] = changes_docs_inputs
            if changed_docs:
                combined_changes.setdefault("changed_docs", []).extend(saved_files_doc)

            # Add timestamps and approval info to the changes
            timestamped_changes = timestamps.add_timestamps(combined_changes)
            timestamped_changes = timestamps.add_approvalInfo(
                timestamped_changes, user_id, _id
            )

            # Insert the timestamped changes into the inventory changes collection
            InventoryChanges.insert_one(timestamped_changes)
        else:
            # Log a message if no changes are present
            print("Ninguno de los valores es un diccionario.")

        # Return a successful response
        return Response("is ok", status=status.HTTP_200_OK)

    def get_module_id(self, module_name, mongo):
        module = mongo.connect("modules").find_one({"name": module_name})
        return module["_id"]

    def put(self, request, _id):

        user_id = request.user.id

        mongo = Mongo()

        changes = mongo.connect("inventory_change_approvals")
        cursor_change = changes.find_one(
            {"piece_id": ObjectId(_id), "approved_rejected": None}
        )

        if cursor_change is not None:
            id_change_fields = {
                "gender_id",
                "subgender_id",
                "type_object_id",
                "dominant_material_id",
            }
            exclusions = {
                "_id",
                "created_at",
                "updated_at",
                "created_by",
                "piece_id",
                "approved_rejected_by",
                "approved_rejected",
                "changed_pics",
                "new_pics",
                "changed_pics_info",
                "new_pics_info",
                "changed_docs",
                "new_docs",
                "changed_docs_info",
                "new_docs_info",
            }

            data_piece_to_update = {
                key: (
                    ObjectId(item["newValue"]["_id"])
                    if key in id_change_fields
                    else item["newValue"]
                )
                for key, item in cursor_change.items()
                if key not in exclusions
            }
            print("cursor_change", cursor_change)

            if "changed_pics" in cursor_change:
                self.process_changed_pics(cursor_change, user_id, _id)
            if "changed_pics_info" in cursor_change:
                self.process_changed_pics_info(cursor_change, user_id, _id)
            if "new_pics" in cursor_change:
                self.process_new_pics(cursor_change, user_id, _id)

            if "changed_docs" in cursor_change:
                self.process_changed_docs(cursor_change, user_id, _id)
            if "changed_docs_info" in cursor_change:
                self.process_changed_docs_info(cursor_change, user_id, _id)
            if "new_docs" in cursor_change:
                self.process_new_docs(cursor_change, user_id, _id)

            try:
                is_approved = request.data.get("isApproved")
                print(is_approved)
                piece = mongo.connect("pieces")
                pieceStateBeforeChanges = piece.find_one({"_id": ObjectId(_id)})
                if is_approved:
                    cursor_piece = piece.update_one(
                        {"_id": ObjectId(_id)}, {"$set": data_piece_to_update}
                    )
                    if cursor_piece.matched_count > 0:

                        pieces_search = mongo.connect("pieces_search")

                        # print("Pieces_one",Pieces_one)
                        PIECES_ALL.insert(0, {"$match": {"_id": ObjectId(_id)}})
                        cursor = piece.aggregate(PIECES_ALL)
                        print("cursor", cursor)
                        for document in cursor:
                            print("document", document)
                            pieces_search.replace_one({"_id": ObjectId(_id)}, document)

                    result = changes.update_one(
                        {"piece_id": ObjectId(_id), "approved_rejected": None},
                        {
                            "$set": {
                                "approved_rejected_by": user_id,
                                "approved_rejected": "approved",
                            },
                            "$push": {"piece_before_changes": pieceStateBeforeChanges},
                        },
                    )

                    if result.modified_count > 0:
                        # borramos serialized para que se vuelva a formar ya que cambio el contenido
                        _ = mongo.checkAndDropIfExistCollection(
                            "pieces_search_serialized"
                        )
                        return Response("piece updated", status=status.HTTP_200_OK)

                else:

                    print("test if not approved")
                    result = changes.update_one(
                        {"piece_id": ObjectId(_id), "approved_rejected": None},
                        {
                            "$set": {
                                "approved_rejected_by": user_id,
                                "approved_rejected": "rejected",
                            }
                        },
                    )
                    if result.modified_count > 0:
                        return Response("piece rejected", status=status.HTTP_200_OK)

            except Exception as e:
                return Response(str(e), status=status.HTTP_400_BAD_REQUEST)

    def process_new_pics(self, cursor_change, user_id, _id):
        mongo = Mongo()
        try:
            moduleId = self.get_module_id("inventory", mongo)
            for pic in cursor_change["new_pics"]:
                newpic = {
                    "photographer": pic["photographer"],
                    "photographed_at": pic["photographed_at"],
                    "description": pic["description"],
                    "file_name": pic["file_name"],
                    "module_id": ObjectId(moduleId),
                    "piece_id": ObjectId(_id),
                    "size": pic["size"],
                    "mime_type": pic["mime_type"],
                }
                audit = AuditManager()
                newpic = audit.add_photoInfo(newpic, user_id)
                mongo.connect("photographs").insert_one(newpic)
                origen = os.path.join(
                    settings.TEMPORARY_UPLOAD_DIRECTORY, pic["file_name"]
                )
                destino = os.path.join(settings.PHOTO_INVENTORY_PATH, pic["file_name"])
                shutil.copy(origen, destino)
                img = Image.open(settings.TEMPORARY_UPLOAD_DIRECTORY + pic["file_name"])
                width_thumbnail = 100
                height_thumbnail = int(img.height * (width_thumbnail / img.width))
                img_thumbnail = img.resize((width_thumbnail, height_thumbnail))
                img_thumbnail.save(
                    settings.THUMBNAILS_INVENTORY_PATH + pic["file_name"]
                )
        except Exception as e:
            return Response(
                {"error": "Can't create the new photo registry " + str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def process_changed_pics(self, cursor_change, user_id, _id):
        mongo = Mongo()
        try:
            moduleId = self.get_module_id("inventory", mongo)
            for pic in cursor_change["changed_pics"]:
                print("pic", pic)

                photo_cursor = mongo.connect("photographs").find_one(
                    {"_id": pic["_id"]}
                )

                # renaming the actual photo beacuse is deletiong but just we gona to change the file name adding one underscore _ and delete i.e Asdweasd_delete.jpg
                origen = os.path.join(
                    settings.PHOTO_INVENTORY_PATH, photo_cursor["file_name"]
                )
                destingo = os.path.join(
                    settings.PHOTO_INVENTORY_PATH,
                    "deleted_" + photo_cursor["file_name"],
                )
                shutil.move(origen, destingo)
                # actualizando la foto en la coleccion
                cursor = mongo.connect("photographs").update_one(
                    {"_id": pic["_id"]},
                    {
                        "$set": {
                            "file_name": pic["file_name"],
                            "size": pic["size"],
                            "mime_type": pic["mime_type"],
                        }
                    },
                )
                # copiando la imagen del temporal al inventario
                if cursor.modified_count > 0:
                    print("se inserto la imagen en la coleccion")
                    origen = os.path.join(
                        settings.TEMPORARY_UPLOAD_DIRECTORY, pic["file_name"]
                    )
                    destino = os.path.join(
                        settings.PHOTO_INVENTORY_PATH, pic["file_name"]
                    )
                    shutil.move(origen, destino)
                    # creando la miniatura
                    img = Image.open(
                        settings.PHOTO_INVENTORY_PATH + pic["file_name"]
                    )
                    width_thumbnail = 100
                    height_thumbnail = int(img.height * (width_thumbnail / img.width))
                    img_thumbnail = img.resize((width_thumbnail, height_thumbnail))
                    img_thumbnail.save(
                        settings.THUMBNAILS_INVENTORY_PATH + pic["file_name"]
                    )

                    origen = os.path.join(
                        settings.TEMPORARY_UPLOAD_DIRECTORY, pic["file_name"]
                    )
                    """
                    destino = os.path.join(
                        settings.TEMPORARY_UPLOAD_DIRECTORY, "used_" + pic["file_name"]
                    )
                    """#este codigo se usa si solo quieres marcar la imagen como usada
                    os.remove(origen)
                    print("se movio la imagen del temporal al inventario")
                else:
                    print("no se inserto la imagen en la coleccion")

            print("ModuleId", moduleId)

        except Exception as e:
            return Response(
                {"error": "Can't create the new photo registry " + str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def process_changed_pics_info(self, cursor_change, user_id, _id):
        mongo = Mongo()

        for pic_info in cursor_change["changed_pics_info"].values():
            pic_id = pic_info["_id"]
            for key, value in pic_info.items():
                if key != "_id":
                    cursor = mongo.connect("photographs").update_one(
                        {"_id": ObjectId(pic_id)}, {"$set": {key: value["newValue"]}}
                    )

    def process_changed_docs(self, cursor_change, user_id, _id):
        mongo = Mongo()
        try:
            moduleId = self.get_module_id("inventory", mongo)
            for doc in cursor_change["changed_docs"]:
                print("docPsc", doc)
                doc_cursor = mongo.connect("documents").find_one({"_id": doc["_id"]})
                print("doc_cursor", doc_cursor)
                origen = os.path.join(
                    settings.DOCUMENT_INVENTORY_PATH, doc_cursor["file_name"]
                )
                destingo = os.path.join(
                    settings.DOCUMENT_INVENTORY_PATH,
                    "deleted_" + doc_cursor["file_name"],
                )
                shutil.move(origen, destingo)
                print("se movio el documento del inventario")
                print("doc[id]", doc["_id"])

                cursor2 = mongo.connect("documents").update_one(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            "file_name": doc["file_name"],
                            "size": doc["size"],
                            "mime_type": doc["mime_type"],
                        }
                    },
                )
                print("cursor.modified_count", cursor2.modified_count)
                if cursor2.modified_count > 0:
                    print("se inserto el documento en la coleccion")
                    origen = os.path.join(
                        settings.TEMPORARY_UPLOAD_DIRECTORY, doc["file_name"]
                    )
                    destino = os.path.join(
                        settings.DOCUMENT_INVENTORY_PATH, doc["file_name"]
                    )
                    shutil.copy(origen, destino)

                    origen = os.path.join(
                        settings.TEMPORARY_UPLOAD_DIRECTORY, doc["file_name"]
                    )
                    destino = os.path.join(
                        settings.TEMPORARY_UPLOAD_DIRECTORY, "used_" + doc["file_name"]
                    )
                    shutil.move(origen, destino)
        except Exception as e:
            return Response(
                {"error": "Can't create the new document registry " + str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def process_changed_docs_info(self, cursor_change, user_id, _id):
        mongo = Mongo()

        for doc_info in cursor_change["changed_docs_info"].values():
            doc_id = doc_info["_id"]
            for key, value in doc_info.items():
                if key != "_id":
                    cursor = mongo.connect("documents").update_one(
                        {"_id": ObjectId(doc_id)}, {"$set": {key: value["newValue"]}}
                    )

    def process_new_docs(self, cursor_change, user_id, _id):
        mongo = Mongo()
        try:
            print("processing new docs")
            print("_id", _id)
            print("user_id", user_id)
            moduleId = self.get_module_id("inventory", mongo)
            print("cursor_change['new_docs']", cursor_change["new_docs"])
            print("type(cursor_change['new_docs'])", type(cursor_change["new_docs"]))
            if cursor_change["new_docs"]:
                print("La lista no está vacía")
            else:
                print("La lista está vacía")
            for doc in cursor_change["new_docs"]:
                print("doc", doc)
                newdoc = {
                    "name": doc["name"],
                    "file_name": doc["file_name"],
                    "module_id": ObjectId(moduleId),
                    "piece_id": ObjectId(_id),
                    "size": doc["size"],
                    "mime_type": doc["mime_type"],
                }
                audit = AuditManager()
                print("audit", audit)
                newdoc = audit.add_documentInfo(newdoc, user_id)
                print("newdocF", newdoc)
                cursor = mongo.connect("documents").insert_one(newdoc)
                print("newdoc", newdoc)
                if cursor.inserted_id:
                    print("se inseto el documento en la coleccion")

                origen = os.path.join(
                    settings.TEMPORARY_UPLOAD_DIRECTORY, doc["file_name"]
                )
                destino = os.path.join(
                    settings.DOCUMENT_INVENTORY_PATH, doc["file_name"]
                )
                shutil.copy(origen, destino)

        except Exception as e:
            return Response(
                {"error": "Can't create the new document registry " + str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
