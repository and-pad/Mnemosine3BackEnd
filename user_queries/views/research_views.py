
from hmac import new
import json

# from turtle import title
from annotated_types import T
from bson import ObjectId

# from collections import defaultdict
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from user_queries.driver_database import mongo
from user_queries.driver_database.mongo import Mongo

from rest_framework.permissions import IsAuthenticated
from .tools import AuditManager
from authentication.views import Permission
from user_queries.mongo_queries import (
    PIECES_ALL,
    inventory_research_edit,
    research_edit,)

from types import SimpleNamespace

from user_queries.shemas.research_shema import ResearchSchema
from user_queries.shemas.photograph_shema import PhotographSchema

from .researchs.document_handler import process_documents
from .researchs.pictures_handler import process_pictures
from .researchs.footnotes_bibliographies_handler import process_footnotes_and_bibliographies
from .researchs.request_data_handler import load_request_data
from .researchs.save_history_handler import save_history_changes
from .researchs.utils import (
    format_new_pic, 
    get_research_id, 
    get_module_id, 
    process_thumbnail, 
    add_delete_to_actual_photo_file_name, 
    store_pic_changes, 
    format_research_data
    )

class ResearchEdit(APIView):

    permission_classes = [IsAuthenticated]

    inventory_fields = [
        "gender_id",
        "subgender_id",
        "type_object_id",
        "dominant_material_id",
        "description_origin",
        "description_inventory",
    ]

    

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
        module_id = get_module_id("research", mongo)
        if not module_id:
            return Response(
                {"response": "Módulo no encontrado"}, status=status.HTTP_400_BAD_REQUEST
            )

        research = list(
            mongo.connect("researchs").aggregate(research_edit(module_id, _id))
        )
        # print("research", research)

        cursor_change_json = {}
        if not research:

            print("No se encontraron registros de investigación... Creando uno nuevo")
            # Si no se encuentra investigación, se crea una nueva
            research = list(
                mongo.connect("pieces_search").aggregate(inventory_research_edit(_id))
            )
            cursor_change_json["inventory_data"] = json.loads(
                json.dumps(research, default=str)
            )
            # print("inventory data",cursor_change_json)
        else:

            cursor_change_json = json.loads(json.dumps(research, default=str))[0]

        # Obtener todos los catálogos en una sola consulta
        catalog_codes = [
            "author",
            "involved_creation",
            "place_of_creation",
            "period",
            "reference_type",
        ]
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

        inv_modifications = list(
            mongo.connect("inventory_change_approvals").find(
                {"piece_id": ObjectId(_id), "approved_rejected": None}
            )
        )

        if inv_modifications:
            cursor_change_json["inventory_modifications"] = self.serialize_mongo_data(
                inv_modifications
            )
            # print("inv_modifications", cursor_change_json["inventory_modifications"])
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


        
    def patch_request_validation(self, request, _id, mongo):
        permissions = Permission()
        perm = permissions.get_permission(request.user)
        # Ya debe estar filtrado esto en el front end pero por refuerzo de seguridad
        # le buscamos en la base de datos

        if "editar_investigacion" not in perm:
            return Response(
                "You have not permission to approve",
                status=status.HTTP_401_UNAUTHORIZED,
            )
        
        
        if not get_module_id("research", mongo):
            return Response(
                {"response": "Módulo no encontrado"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Buscar investigación existente
        
        return mongo.connect("researchs").find_one(
            {"piece_id": ObjectId(_id), "deleted_at": None}
        )
    def validate_research(self, research, request, _id, mongo):
        is_new_research = False
        if not research:
            is_new_research = True
            timestamps = AuditManager()
            research_data = {"piece_id": ObjectId(_id)}
            research_data = timestamps.add_timestampsInfo(
                research_data, request.user.id
            )             
            self.create_research(ResearchSchema(**research_data))
            research = mongo.connect("researchs").find_one(
                {"piece_id": ObjectId(_id), "deleted_at": None}
            )

        return is_new_research, research

   


    def patch(self, request, _id):
        mongo = Mongo()
        
        research = self.patch_request_validation(request, _id, mongo)
        is_new_research, research = self.validate_research(research, request, _id, mongo)        
        
        (changes, pics_new, changed_pics, changes_pics_inputs, new_footnotes, new_bibliographies, changes_bibliographies, changes_footnotes, new_docs, changes_docs) = load_request_data(request)        
        #print("raw changes_pics inputs", changes_pics_inputs)    
        ( ids_saved_footnotes, ids_saved_bibliographies, ids_updated_footnotes, before_update_footnotes, ids_updated_bibliographies, before_update_bibliographies) = process_footnotes_and_bibliographies(request, _id, new_footnotes, new_bibliographies, changes_bibliographies,changes_footnotes)        
        #print("changes_docs", changes_docs)
        documents = process_documents(request, changes_docs,  new_docs, _id, get_module_id("research", mongo))
        print("documents", documents)
        data_pics = process_pictures(request, pics_new, changed_pics,changes_pics_inputs )
        #print("changes post proccess_pics", changes)
        #print("New data_pics", data_pics)
        
        # Si no hay cambios, no se hace nada
        
        user_id = request.user.id        
       
        """
        if changes_pics_inputs and len(changes_pics_inputs) > 0:
            changes.setdefault("changes_pics_inputs", changes_pics_inputs)
        """
        if changes or data_pics:
            self.process_inventory_data(changes, user_id, _id)
            result = self.save_research_changes(changes, data_pics, user_id, _id, is_new_research)

        else:
            result = SimpleNamespace(modified_count=0)            
        
           
        changes_data = {
        "changes": changes,
        "changes_pics_inputs": changes_pics_inputs,
        "changed_pics": changed_pics,
        "new_footnotes": new_footnotes,
        "ids_saved_footnotes": ids_saved_footnotes,
        "new_bibliographies": new_bibliographies,
        "changes_footnotes": changes_footnotes,
        "before_update_footnotes": before_update_footnotes,
        "changes_bibliographies": changes_bibliographies,
        "before_update_bibliographies": before_update_bibliographies,
        "documents": documents
        }
        
        save_history_changes(_id, user_id, research, is_new_research, changes_data)
        
        return Response(
            {
                "response": "Investigación actualizada",
                "modified_count": result.modified_count,
            },
            status=status.HTTP_200_OK,
        )


    def get_json_data(self, request, key, default={}):
        return json.loads(request.data.get(key, default))

    def process_changes(self, request, key):
        changes = self.get_json_data(request, key)
        for key, value in changes.items():
            if "_id" in value and isinstance(value["_id"], str):
                value["_id"] = ObjectId(value["_id"])
        print(changes)
        return changes

    def process_inventory_data(self, data, user_id, _id):        
        if inventoryData := {
            key: value
            for key, value in data.items()
            if key in self.inventory_fields
        }:            
            
            self.save_approval_inventory_data(inventoryData, user_id, _id)

    def save_approval_inventory_data(self, data, user_id, _id):
        mongo = Mongo()

        timestamps = AuditManager()

        InventoryChanges = mongo.connect("inventory_change_approvals")
        combined_changes = {}
        if data:
            combined_changes = {**combined_changes, **data}

        timestamped_changes = timestamps.add_timestampsUpdate(combined_changes)
        timestamped_changes = timestamps.add_approvalInfo(
            timestamped_changes, user_id, _id
        )
        timestamped_changes["changed_by_module_id"] = ObjectId(get_module_id("research", mongo))
        # Insert the timestamped changes into the inventory changes collection
        InventoryChanges.insert_one(timestamped_changes)

    def create_research(self, research_data: ResearchSchema):
        # Convertimos el objeto de Pydantic en diccionario limpio
        doc = research_data.model_dump(
            exclude_none=False
        )  # o exclude_defaults=True si quieres aún más limpio        
        researchs_collection = Mongo().connect("researchs")
        result = researchs_collection.insert_one(doc)
        print("result create", result.inserted_id)
        return result

    def save_research_changes(self, changes, data_pics, user_id, _id, is_new_research):
        
        research = Mongo().connect("researchs").find_one({"piece_id": ObjectId(_id), "deleted_at": None})
        researchData = format_research_data(changes, self.inventory_fields )
        # Siempre agregar usuario que actualizó
        if not is_new_research:
            researchData["updated_by"] = user_id
        print("researchData", researchData)
        # Aplicar actualización
        result = Mongo().connect("researchs").update_one({"_id": research["_id"]}, {"$set": researchData})       
        self._process_all_pics(data_pics, user_id, _id)
        self._refresh_changes_in_db(_id)

        return result    
    
    def _refresh_changes_in_db(self, _id):
        piece = Mongo().connect("pieces")
        pieces_search = Mongo().connect("pieces_search")       
        #PIECES_ALL es una consulta mongo grande para obtener todos los datos para enviar al front end
        #Aqui se le agrega el filtro por id de pieza, para que solo se actualice la pieza que se ha editado
        PIECES_ALL.insert(0, {"$match": {"_id": ObjectId(_id)}})        
        cursor = piece.aggregate(PIECES_ALL)
        # print("cursor", cursor)
        for document in cursor:
            #reemplazamos el documento porque ha sido editado
            pieces_search.replace_one({"_id": ObjectId(_id)}, document)
        # borramos la coleccion de busqueda de piezas serializadas
        # para que se vuelva a crear con los datos actualizados
        Mongo().checkAndDropIfExistCollection("pieces_search_serialized")
            
    def _process_all_pics(self, data_pics, user_id, _id):
        if data_pics.get("new_pics"):
            print("new_pics", data_pics["new_pics"])
        self.process_new_pics(data_pics, user_id, _id)        
        
        if data_pics.get("changed_pics"):
            print("changed_pics", data_pics["changed_pics"])
            self.process_changed_pics(data_pics, user_id)


        if data_pics.get("changes_pics_inputs"):
            print("changes_pics_inputs", data_pics["changes_pics_inputs"])
            self.process_changed_pics_inputs(data_pics, user_id )
                # Aquí podrías procesar los cambios de entradas de fotos si es necesario
    def process_new_pics(self, cursor_change, user_id, _id):
        mongo = Mongo()
        #try:
        moduleId = get_module_id("research", mongo)   
        #print("cursor_change", cursor_change)
        if cursor_change.get("new_pics") and len(cursor_change["new_pics"]) > 0:
            for pic in cursor_change["new_pics"]:
                # este es el objeto como debe ser guardado en la base, su shema.                                                             
                mongo.connect("photographs").insert_one(PhotographSchema(**format_new_pic(pic, user_id, moduleId, _id)).model_dump())                
                process_thumbnail(pic)               
            #except Exception as e:
                #print(f"Error al procesar nuevas fotos: {e}")
                # Habra errores en caso de falta de permisos o que no exista la carpeta
                # se debe corregir el error ya que no se puede guardar
                #return e
        
   
    def process_changed_pics(self, cursor_change, user_id):
        mongo = Mongo()
        try:
            #moduleId = get_module_id("research", mongo)
            #print("cursor_change", cursor_change["changed_pics"])
            for  pic in cursor_change["changed_pics"]:
                photo_cursor = mongo.connect("photographs").find_one(
                    {"_id": ObjectId(pic["_id"])}
                )
                add_delete_to_actual_photo_file_name(photo_cursor["file_name"])                
                store_pic_changes(pic, user_id)                
                process_thumbnail(pic)
                #if cursor.modified_count > 0:
                    #print(f"Foto actualizada: {pic['_id']}")

        except Exception as e:
            print(f"Error al procesar fotos cambiadas: {e}")
    
    def process_changed_pics_inputs(self, cursor_change, user_id):      
        
        try:        
            for index,pic in cursor_change["changes_pics_inputs"].items():
                audit_pic = AuditManager()
                
                to_update = {
                "photographer": pic.get("photographer", {}).get("newValue") or None,
                "photographed_at": pic.get("photographed_at", {}).get("newValue") or None,
                "description": pic.get("description", {}).get("newValue") or None,
                }
                
                to_update = audit_pic.add_updateInfo(to_update, user_id)
                PhotographSchemaChanges = PhotographSchema(**to_update)
                print("pic_id", pic["_id"])
                print(PhotographSchemaChanges.model_dump(exclude_none=True))
                Mongo().connect("photographs").update_one(
                    {"_id": ObjectId(pic["_id"])},
                    {
                        "$set": PhotographSchemaChanges.model_dump(exclude_none=True),
                    },
                )
                
        except Exception as e:
            print(f"Error al procesar entradas de fotos cambiadas: {e}")
