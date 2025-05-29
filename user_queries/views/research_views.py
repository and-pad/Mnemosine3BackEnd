import os
import random
import string

import json
import shutil
from tkinter import S

#from turtle import title
from bson import ObjectId
#from collections import defaultdict
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from user_queries.driver_database.mongo import Mongo

from rest_framework.permissions import IsAuthenticated
from .tools import AuditManager
from authentication.views import Permission
from user_queries.mongo_queries import (
    PIECES_ALL,
    inventory_research_edit,
    research_edit
)
from datetime import datetime
from types import SimpleNamespace
from django.conf import settings
from PIL import Image
from user_queries.shemas.research_shema import ResearchSchema


class ResearchEdit(APIView):
    
    permission_classes = [IsAuthenticated]
    
    inventory_fields =["gender_id", "subgender_id", "type_object_id", "dominant_material_id", "description_origin", "description_inventory"]
    def get_module_id(self, module_name, mongo):
        """Obtiene el ID de un módulo por su nombre."""
        module = mongo.connect("modules").find_one(
            {"name": module_name, "deleted_at": None}, {"_id": 1}
        )
        return module["_id"] if module else None

    def get_genders(self, mongo):
        """Obtiene todos los géneros en una sola consulta."""
        genders = mongo.connect("genders").find({"deleted_at": None}, {"title": 1})
        if not genders:
            return []

        genders = list(genders)
        return self.serialize_mongo_data(genders)

    def get_subgenders(self, mongo):
        """Obtiene todos los subgéneros en una sola consulta."""
        subgenders = mongo.connect("subgenders").find(
            {"deleted_at": None}, {"title": 1, "gender_id": 1}
        )
        if not subgenders:
            return []

        subgenders = list(subgenders)
        return self.serialize_mongo_data(subgenders)

    def get(self, request, _id):
        mongo = Mongo()
        module_id = self.get_module_id("research", mongo)
        if not module_id:
            return Response(
                {"response": "Módulo no encontrado"}, status=status.HTTP_400_BAD_REQUEST
            )

        research = list(
            mongo.connect("researchs").aggregate(research_edit(module_id, _id))
        )
        print("research", research)
        
        cursor_change_json = {}
        if not research:
                        
            print("No se encontraron registros de investigación... Creando uno nuevo")
            # Si no se encuentra investigación, se crea una nueva            
            research = list(mongo.connect("pieces_search").aggregate(inventory_research_edit(_id)))
            cursor_change_json["inventory_data"] = json.loads(json.dumps(research, default=str))            
            #print("inventory data",cursor_change_json)            
        else:
            
            cursor_change_json = json.loads(json.dumps(research, default=str))[0]
            
        # Obtener todos los catálogos en una sola consulta
        catalog_codes = ["author", "involved_creation", "place_of_creation", "period", "reference_type"]
        catalog_ids = self.get_catalog_ids(mongo, catalog_codes)
        all_catalogs = {
            code: self.get_catalog_elements(mongo, catalog_id)
            for code, catalog_id in catalog_ids.items()
        }

        catalog_code = ["object_type", "dominant_material"]
        catalog_ids = self.get_catalog_ids(mongo, catalog_code)

        all_object_type = {
            code: self.get_catalog_elements(mongo, catalog_id)
            for code, catalog_id in catalog_ids.items()
        }
        
        

        researchs_documents = mongo.connect("documents").find(
            {"piece_id": ObjectId(_id), "deleted_at": None, "module_id": module_id}
        )
        researchs_documents = list(researchs_documents)
        cursor_change_json["documents"] = self.serialize_mongo_data(researchs_documents)

        researchs_photos = mongo.connect("photographs").find(
            {"piece_id": ObjectId(_id), "deleted_at": None, "module_id": module_id}
        )
        researchs_photos = list(researchs_photos)
        cursor_change_json["photos"] = self.serialize_mongo_data(researchs_photos)
        
        inv_modifications = list(mongo.connect("inventory_change_approvals").find({"piece_id": ObjectId(_id), "approved_rejected": None}))
        
        if inv_modifications:
            cursor_change_json["inventory_modifications"] = self.serialize_mongo_data(inv_modifications)
            #print("inv_modifications", cursor_change_json["inventory_modifications"])
        else:
            cursor_change_json["inventory_modifications"] = []
            
            # print("all_object_type",all_object_type.get("dominant_material", []))
        # print("period",period_research)
        return Response(
            {
                "research_data": cursor_change_json,
                "all_authors": all_catalogs.get("author", []),
                "all_involved_creation": all_catalogs.get("involved_creation", []),
                "all_place_of_creation": all_catalogs.get("place_of_creation", []),
                "all_period": all_catalogs.get("period", []),
                "all_genders": self.get_genders(mongo),
                "all_subgenders": self.get_subgenders(mongo),
                "all_object_type": all_object_type.get("object_type", []),
                "all_dominant_material": all_object_type.get("dominant_material", []),
                "all_references_type": all_catalogs.get("reference_type", []),
            },
            status=status.HTTP_200_OK,
        )

    def get_catalog_ids(self, mongo, catalog_codes):
        """Obtiene los ObjectId de los catálogos en una sola consulta."""
        catalogs = mongo.connect("catalogs").find(
            {"code": {"$in": catalog_codes}, "deleted_at": None}, {"code": 1, "_id": 1}
        )
        return {cat["code"]: cat["_id"] for cat in catalogs}

    def get_catalog_elements(self, mongo, catalog_id):
        """Obtiene todos los elementos de un catálogo por su ObjectId."""
        if not catalog_id:
            return []
        elements = list(
            mongo.connect("catalog_elements").find(
                {"catalog_id": ObjectId(catalog_id), "deleted_at": None}, {"title": 1}
            )
        )
        return self.serialize_mongo_data(elements)

    def get_research_data(self, mongo, data, field):
        """Obtiene los datos relacionados a un campo específico del research."""
        ids = data.get(field, [])
        if not isinstance(ids, list) or not ids:
            return []

        # Consulta optimizada para traer todos los elementos en una sola búsqueda
        elements = list(
            mongo.connect("catalog_elements").find(
                {"_id": {"$in": [ObjectId(i) for i in ids if ObjectId.is_valid(i)]}},
                {"_id": 1, "title": 1},
            )
        )
        return self.serialize_mongo_data(elements)

    def serialize_mongo_data(self, data):
        """Serializa datos de MongoDB a JSON serializable."""
        return json.loads(json.dumps(data, default=str))

    
    def patch(self, request, _id):
        
        permissions = Permission()
        perm = permissions.get_permission(request.user)
        # Ya debe estar filtrado esto en el front end pero por refuerzo de seguridad
        # le buscamos en la base de datos

        if "editar_investigacion" not in perm:
            return Response(
                "You have not permission to approve",
                status=status.HTTP_401_UNAUTHORIZED,
            )
        
        mongo = Mongo()
        module_id = self.get_module_id("research", mongo)
        if not module_id:
            return Response(
                {"response": "Módulo no encontrado"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Buscar investigación existente
        research = mongo.connect("researchs").find_one(
            {"piece_id": ObjectId(_id), "deleted_at": None}
        )
        
        is_new_research = False
        if not research:
            is_new_research = True
            timestamps = AuditManager()            
            research_data = {"piece_id": ObjectId(_id)}
            research_data = timestamps.add_timestampsInfo(research_data, request.user.id)
            research_data = ResearchSchema(**research_data)
            result = self.create_research(research_data)            
            research = mongo.connect("researchs").find_one(
                {"piece_id": ObjectId(_id), "deleted_at": None}
            )
            
            for key, value in research.items():        
                print("key", key)
                print("value", value)
            
        changes = json.loads(request.data.get("changes", "{}"))
        pics_new = json.loads(request.data.get("PicsNew", "{}"))
        changed_pics = json.loads(request.data.get("changed_pics", "{}"))
        changes_pics_inputs = json.loads(request.data.get("changes_pics_inputs", "{}"))
        
        
              # Process new pictures
        for index, pic in enumerate(pics_new):
            #print("index", index)
            #print("pic", pic)            
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
                #print("changes", changes)
                # Save the file 
                self.save_image_files(file, filename)
        
        
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
                    self.save_image_files(file, filename)
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
  
        
        user_id = request.user.id
        #print("changes", changes)
        # Procesamiento previo (si aplica, por ejemplo, para log o auditoría)
        
        if changes_pics_inputs and len(changes_pics_inputs) > 0:
            changes.setdefault("changes_pics_inputs", changes_pics_inputs)
        
        #self.process_changes(request, "changes_pics_inputs")
        #print(request.data)
        # Guardar cambios en la colección
        if changes:            
            
            self.process_inventory_data(changes, user_id, _id)
            result = self.save_research_changes(changes, user_id, _id, is_new_research)
            
        else:
            result = SimpleNamespace(modified_count=0)
            
            """
            if result.modified_count > 0:
                mongo.connect("research_changes_history").insert_one(
                    {
                        "piece_id": ObjectId(_id),
                        "research_id": research["_id"],
                        "research_before_of_changes": research, #research before of changes
                        "updated_by": user_id,
                        "updated_at": datetime.now(),
                        "changes": changes
                        
                    }
                )
            """
            
        ResearchChanges = mongo.connect("research_changes_history")

        if any(
            isinstance(x, dict)
            for x in [
                changes,
                changes_pics_inputs,
                changed_pics,
                #changes_docs_inputs,
                #changed_docs,
            ]
        ):
            timestamps = AuditManager()
            combined_changes = {}
            

            # Combine changes into a single dictionary
            if changes:
                combined_changes = {**combined_changes, **changes}
            if changes["new_pics"]:                
                combined_changes.setdefault("new_pics", []).extend(changes["new_pics"]) 
            
            if changes_pics_inputs and len(changes_pics_inputs) > 0:
                combined_changes["changes_pics_inputs"] = changes_pics_inputs
            if changed_pics:
                combined_changes.setdefault("changed_pics", []).extend(saved_files_img)
            
            #if changes_docs_inputs:
                #combined_changes["changed_docs_info"] = changes_docs_inputs
            #if changed_docs:
                #combined_changes.setdefault("changed_docs", []).extend(saved_files_doc)

            # Add timestamps and approval info to the changes
            timestamped_changes = timestamps.add_timestampsResearch(combined_changes, user_id,research, is_new_research)            

            # Insert the timestamped changes into the inventory changes collection
            ResearchChanges.insert_one(timestamped_changes)
            
            
            

        return Response(
            {
                "response": "Investigación actualizada",
                "modified_count": result.modified_count
            },
            status=status.HTTP_200_OK
        )

    def generate_random_file_name(self, original_filename, length=40):
        _, extension = os.path.splitext(original_filename)
        alphabet = string.ascii_letters + string.digits
        return "".join(random.choices(alphabet, k=length)) + extension
    
    def get_json_data(self, request, key, default={}):
        return json.loads(request.data.get(key, default))
        

    def process_changes(self, request, key):
        changes = self.get_json_data(request, key)
        for key, value in changes.items():
            if "_id" in value and isinstance(value["_id"], str):
                value["_id"] = ObjectId(value["_id"])
        print(changes)
        return changes
    
    def process_inventory_data(self, data,user_id, _id):        
        inventoryData = {}        
        for key, value in data.items():
            if key in self.inventory_fields:
                        
                inventoryData[key] = value
                #print("key", key)
                #print("value", value)        
                
        
        if inventoryData:    
            #print("se salvo inventory")
            self.save_approval_inventory_data(inventoryData, user_id, _id)        
                
    def save_approval_inventory_data(self, data, user_id, _id):
        mongo = Mongo()
        
        timestamps = AuditManager()

        InventoryChanges = mongo.connect("inventory_change_approvals")
        combined_changes = {}
        if data:
                combined_changes = {**combined_changes, **data}
                
        timestamped_changes = timestamps.add_timestamps(combined_changes)
        timestamped_changes = timestamps.add_approvalInfo(
                timestamped_changes, user_id, _id
            )

            # Insert the timestamped changes into the inventory changes collection
        InventoryChanges.insert_one(timestamped_changes)        
    
    def create_research(self, research_data: ResearchSchema):
        # Convertimos el objeto de Pydantic en diccionario limpio
        doc = research_data.model_dump(exclude_none=False)  # o exclude_defaults=True si quieres aún más limpio
        mongo = Mongo()
        researchs_collection = mongo.connect("researchs")
        result = researchs_collection.insert_one(doc)
        print("result create", result.inserted_id)
        return result
    
    
    def save_research_changes(self, changes, user_id, _id, is_new_research):
        mongo = Mongo()
        db = mongo.connect("researchs")

        # Buscar el documento existente
        research = db.find_one({"piece_id": ObjectId(_id), "deleted_at": None})
        if not research:
            print("changes",changes)
            
            #new_research = ResearchSchema(**changes)
            
            #raise ValueError("Investigación no encontrada")
        # Campos que requieren conversión especial
        field_map = {
            "authors": "author_ids",
            "period": "period_id",
            "place_of_creation": "place_of_creation_id",
            "involved_creation": "involved_creation_ids"
        }

        researchData = {}

        for key, value in changes.items():
            #print("key", key)
            if key not in self.inventory_fields:
                if not isinstance(value, dict) or "newValue" not in value:
                    continue

                new_value = value["newValue"]
                mapped_key = field_map.get(key, key)

                # Convertir listas de objetos a listas de ObjectId
                if isinstance(new_value, list):
                    ids = []
                    for item in new_value:
                        if isinstance(item, dict) and "_id" in item:
                            try:
                                ids.append(ObjectId(item["_id"]))
                            except Exception as e:
                                print(f"⚠️ Error al convertir ID en {key}: {item['_id']} ({e})")
                    researchData[mapped_key] = ids

                # Convertir objeto único a ObjectId
                elif isinstance(new_value, dict) and "_id" in new_value:
                    try:
                        researchData[mapped_key] = ObjectId(new_value["_id"])
                    except Exception as e:
                        print(f"⚠️ Error al convertir ID en {key}: {new_value['_id']} ({e})")

                # Guardar valores simples (str, None, etc.)
                elif isinstance(new_value, (str, type(None))):
                    researchData[mapped_key] = new_value

                else:
                    print(f"⚠️ Formato no reconocido para '{key}': {new_value}")

        # Siempre agregar usuario que actualizó
        if not is_new_research:
            researchData["updated_by"] = user_id
        print("researchData", researchData)
        # Aplicar actualización
        result = db.update_one(
            {"_id": research["_id"]},
            {"$set": researchData}
        )
        
            
        if changes.get("new_pics"):
            print("new_pics", changes["new_pics"])
            self.process_new_pics(changes, user_id, _id)
            #mongo.connect("photographs").insert_many(changes["new_pics"])
            _ = mongo.checkAndDropIfExistCollection(
                            "pieces_search_serialized"
                        )
                    
        piece = mongo.connect("pieces")
        pieces_search = mongo.connect("pieces_search")

        # print("Pieces_one",Pieces_one)
        PIECES_ALL.insert(0, {"$match": {"_id": ObjectId(_id)}})
        cursor = piece.aggregate(PIECES_ALL)
        #print("cursor", cursor)
        for document in cursor:
            #print("document", document)
            pieces_search.replace_one({"_id": ObjectId(_id)}, document)

        return result

    def save_image_files(self, file, filename):
        file_path = f"{settings.PHOTO_RESEARCH_PATH}{filename}"
        with open(file_path, "wb") as f:
            for chunk in file.chunks():
                f.write(chunk)
                
                
    def process_new_pics(self, cursor_change, user_id, _id):
        mongo = Mongo()
        try:
            moduleId = self.get_module_id("research", mongo)
            for pic in cursor_change["new_pics"]:
                #este es el objeto como debe ser guardado en la base, su shema
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
                # Con AuditManager le agregamos info de timestamps y auditoria de usuario
                audit = AuditManager()
                newpic = audit.add_photoInfo(newpic, user_id)
                # Guardamos el objeto en la base de datos
                result = mongo.connect("photographs").insert_one(newpic)
                # Hacemos el thumbnail
                # Tomamos el archivo de la carpeta de fotos
                origin = os.path.join(settings.PHOTO_RESEARCH_PATH, pic["file_name"])
                # Creamos el thumbnail en la carpeta de thumbnails
                destination = os.path.join(settings.THUMBNAILS_RESEARCH_PATH, pic["file_name"])
                # Creamos el objeto Image para abrir la imagen y cambiarle el tamaño 
                img = Image.open(origin)
                # Tamaño del thumbnail
                width_thumbnail = 100
                height_thumbnail = int(img.height * (width_thumbnail / img.width))                   
                # Creamos el thumbnail cambiandole el tamaño ajustado a la proporcion anterior
                img_thumbnail = img.resize((width_thumbnail, height_thumbnail))
                # Guardamos el thumbnail
                img_thumbnail.save(destination)        
        except Exception as e:
            # Habra errores en caso de falta de permisos o que no exista la carpeta
            # se debe corregir el error ya que no se puede guardar
            return e
    def _add_delete_to_actual_file_name(self, file_name):
        origin = os.path.join(settings.PHOTO_RESEARCH_PATH, file_name)
        destination = os.path.join(settings.PHOTO_RESEARCH_PATH, "deleted_" + file_name)
        # Esto puede salir mal por falta de permisos, pero le hacemos una comprobacion de error y seguimos
        
        try:
            shutil.move(origin, destination)
        except Exception as e:
            print(e)
    def process_changed_pics(self, cursor_change):
        mongo = Mongo()
        try:
            moduleId = self.get_module_id("research", mongo)
            for pic in cursor_change["changed_pics"]:
                photo_cursor = mongo.connect("photographs").find_one(
                    {"_id": pic["_id"]}
                )
                self._add_delete_to_actual_file_name(photo_cursor["file_name"])
                
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
                if cursor.modified_count > 0:
                    pass
                    
                

            
        except Exception as e:
            return e
    
    def get_module_id(self, module_name, mongo):
        module = mongo.connect("modules").find_one({"name": module_name})
        return module["_id"] if module else None
    