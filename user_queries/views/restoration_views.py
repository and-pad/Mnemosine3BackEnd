
from bson import ObjectId
import json

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from user_queries.driver_database.mongo import Mongo
from rest_framework.permissions import IsAuthenticated
from .tools import AuditManager
from authentication.views import Permission
from .restorations.request_data_handler import load_request_data
from .restorations.document_handler import process_documents
from .restorations.pictures_handler import process_pictures
from user_queries.driver_database.mongo import Mongo
from .common.utils import (format_new_pic, format_restoration_data,
                           get_module_id,
                           process_thumbnail,
                           add_delete_to_actual_photo_file_name,
                           store_pic_changes,
                           format_restoration_data
                           )
from user_queries.shemas.photograph_shema import PhotographSchema
from authentication.custom_jwt import CustomJWTAuthentication
from user_queries.shemas.restorations_shema import RestorationsShema
from user_queries.mongo_queries import PIECES_ALL
from types import SimpleNamespace

def restorations_select(_id):

    return [
        # 1. Restauraciones de la pieza
        {"$match": {"piece_id": ObjectId(_id)}},
        {"$match": {"$expr": {"$eq": ["$deleted_at", None]}}},        
        # 2. Join con fotografías
        {
            "$lookup": {
                "from": "photographs",
                "localField": "photographs_ids",
                "foreignField": "_id",
                "as": "photo_info",
            }
        },
        {"$sort": {"treatment_date": 1}},  # 1 para ascendente, -1 para descendente
    ]


class RestorationEditSelect(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def get(self, request, _id):
        mongo = Mongo()

        restorations_cursor = mongo.connect("restorations").aggregate(
            restorations_select(_id)
        )
        restorations = list(restorations_cursor)
        #print("restorations", restorations)
        # restorations_photos = mongo.connect("restorations_photos").find({"restoration_id": {"$in": [ObjectId(restoration["_id"]) for #restoration in restorations]}})

        restorations_json = json.loads(json.dumps(restorations, default=str))

        return Response({"restorations": restorations_json}, status=status.HTTP_200_OK)


class RestorationEdit(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def get(self, request, _id, restoration_id):
        mongo = Mongo()

        restoration = (
            mongo
            .connect("restorations")
            .find_one({"_id": ObjectId(restoration_id), "piece_id": ObjectId(_id)})
        )
        
        catalog_responsible_id = mongo.connect("catalogs").find_one({"code": "responsible_restorer"})["_id"] 

        catalog_responsible = list(mongo.connect("catalog_elements").find({"catalog_id": catalog_responsible_id}))                        
        catalog_responsible = json.loads(json.dumps(catalog_responsible, default=str))
        #print("catalog_responsible", catalog_responsible)

        module_id = mongo.connect("modules").find_one({"name": "restoration"})["_id"]
        
        photographs_ids = restoration.get("photographs_ids", [])        
        
        if photographs_ids:           
            photos = list(
                mongo.connect("photographs").find({
                    "_id": {"$in": photographs_ids},
                    "module_id": module_id,
                    "deleted_at": None
                })
            )
            photos = json.loads(json.dumps(photos, default=str))
        else:
            photos = []
        #print("photos", photos)

        documents_ids = restoration.get("documents_ids", [])
        if documents_ids:
            documents = list(
                mongo.connect("documents").find({
                    "_id": {"$in": documents_ids},
                    "module_id": module_id,
                    "deleted_at": None
                })
            )
            documents = json.loads(json.dumps(documents, default=str))
        else:
            documents = []
        #print("documents", documents)
        
        restoration = json.loads(json.dumps(restoration, default=str))

        return Response(
            {
            "restoration": restoration,
            "catalog_responsible": catalog_responsible,
            "photos": photos,
            "documents": documents,
            }, status=status.HTTP_200_OK
        )


    
    def patch(self, request, _id, restoration_id):
        mongo = Mongo()
        restoration = self.patch_request_validation(request, _id, restoration_id, mongo)
        (changes,
        pics_new,
        changed_pics,
        changes_pics_inputs,        
        new_docs,
        changes_docs,) = load_request_data(request)
        print("changes", changes)        
        print("pics_new", pics_new)
        user_id = request.user.id        
        result = None
        with mongo.start_session() as session:
            try:
                with session.start_transaction():
                    moduleId = self.get_module_id("restoration", mongo)
                    ids_actual_docs = list(restoration.get("documents_ids", []))
                    actualized_doc_ids, documents = process_documents(request, ids_actual_docs, changes_docs, new_docs, _id, moduleId, mongo, session)
                    data_pics = process_pictures(request, pics_new, changed_pics,changes_pics_inputs )


                    if changes or data_pics :                    
                        result = self.save_restoration_changes(changes, data_pics,actualized_doc_ids, user_id, _id, restoration_id, restoration, mongo, session)
                    else:
                        result = SimpleNamespace(modified_count=0)     

                    changes_data = {
                        "piece_id": ObjectId(_id),
                        "restoration_id": ObjectId(restoration_id),                        
                        "changes": changes,
                        "changes_pics_inputs": changes_pics_inputs,
                        "changed_pics": changed_pics,
                        "new_pics": pics_new,
                        "new_docs": new_docs,
                        "changes_docs": changes_docs,
                        "documents": documents,
                        "restoration_before_changes": restoration,
                    }

                    history_set =AuditManager().add_timestampsInfo(changes_data, ObjectId(user_id))
                    mongo.connect("restoration_changes_history").insert_one(history_set, session=session)
                    
        
            except Exception as e:       
                # Si hubo error dentro del with start_transaction
                # Mongo aborta la transacción automáticamente.
                print(f"Error al procesar todo: {e}")
                raise
        
        if not result:
            return Response({"response": "No se realizaron cambios"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"response": "Restauración actualizada"}, status=status.HTTP_200_OK)

    def save_restoration_changes(self, changes, data_pics, actualized_doc_ids, user_id, _id, restoration_id, restoration, mongo, session):               
        #leemos la restauración y verificamos que exista
        added_pics_ids = []
        
        if data_pics:
           
           added_pics_ids = self._process_all_pics(data_pics, user_id, _id, restoration_id, restoration, mongo, session)
        
        existent_photos = restoration.get("photographs_ids")
        changes_photos = added_pics_ids if existent_photos != added_pics_ids else []        
        print("changes_photos", changes_photos)
        
        if actualized_doc_ids != restoration.get("documents_ids", []):
            changes["documents_ids"] = {
                "newValue": actualized_doc_ids
            }
            print("changes updated with documents", changes)

        if changes or changes_photos:
            if changes_photos:
                changes["photographs_ids"] = {
                    "newValue": changes_photos
                }
                print("changes updated with photos", changes)

        

        
            restorationData = format_restoration_data(changes)
            
            AuditManager().add_updateInfo(restorationData, ObjectId(user_id))
            #restorationData["updated_by"] = ObjectId(user_id)

            shemaRestoration = RestorationsShema(**restorationData).model_dump(exclude_none=True) 
            result =mongo.connect("restorations").update_one(
                {"_id": ObjectId(restoration_id)},
                {
                    "$set": shemaRestoration,
                },
                session=session
            )
            self._refresh_changes_in_db(_id, mongo, session)

        return result or None


            
    def _refresh_changes_in_db(self, _id, mongo, session):
        piece = mongo.connect("pieces")
        pieces_search = mongo.connect("pieces_search")       
        #PIECES_ALL es una consulta mongo grande para obtener todos los datos para enviar al front end
        #Aqui se le agrega el filtro por id de pieza, para que solo se actualice la pieza que se ha editado
        PIECES_ALL.insert(0, {"$match": {"_id": ObjectId(_id)}})        
        cursor = piece.aggregate(PIECES_ALL, session=session)
        # print("cursor", cursor)
        for document in cursor:
            #reemplazamos el documento porque ha sido editado
            pieces_search.replace_one({"_id": ObjectId(_id)}, document, session=session)
        # borramos la coleccion de busqueda de piezas serializadas
        # para que se vuelva a crear con los datos actualizados
        mongo.checkAndDropIfExistCollection("pieces_search_serialized")           


    def _process_all_pics(self, data_pics, user_id, _id, restoration_id, restoration, mongo, session):        
                
        photographs_ids = self.process_new_pics(data_pics, user_id, _id, mongo, session) 
        self.process_changed_pics(data_pics, user_id, mongo, session)        
        self.process_changed_pics_inputs(data_pics, user_id, mongo, session)
        raw_photos = restoration.get("photographs_ids")
        # Normalizas:
        raw_photos = raw_photos if isinstance(raw_photos, list) else []
        added_photographs_ids = raw_photos + photographs_ids                     
        print("photographs_ids", added_photographs_ids)
        print("raw_photos", raw_photos)
        print("added_photographs_ids", added_photographs_ids)
        return added_photographs_ids



    def process_changed_pics_inputs(self, cursor_change, user_id, mongo, session):      
        
        try:        
            if cursor_change.get("changes_pics_inputs"):
                for index,pic in cursor_change["changes_pics_inputs"].items():
                    audit_pic = AuditManager()
                    
                    to_update = {
                    "photographer": pic.get("photographer", {}).get("newValue") or None,
                    "photographed_at": pic.get("photographed_at", {}).get("newValue") or None,
                    "description": pic.get("description", {}).get("newValue") or None,
                    }
                    
                    to_update = audit_pic.add_updateInfo(to_update, ObjectId(user_id))
                    PhotographSchemaChanges = PhotographSchema(**to_update)
                    #print("pic_id", pic["_id"])
                    #print(PhotographSchemaChanges.model_dump(exclude_none=True))
                    mongo.connect("photographs").update_one(
                        {"_id": ObjectId(pic["_id"])},
                        {
                            "$set": PhotographSchemaChanges.model_dump(exclude_none=True),
                        },
                        session=session
                    )
                
        except Exception as e:
            print(f"Error al procesar entradas de fotos cambiadas: {e}")
            raise Exception(f"Error al procesar entradas de fotos cambiadas: {e}")


    
    def process_new_pics(self, data_pics, user_id, _id, mongo, session):
        photographs_ids = []
        print("data_pics", data_pics)
        if data_pics.get("new_pics"):
            #mongo = Mongo()
            moduleId = get_module_id("restoration", mongo)
        
            for new_pic in data_pics["new_pics"]:
                # este es el objeto como debe ser guardado en la base, su shema.                                                                           
                result = mongo.collection("photographs").insert_one(PhotographSchema(**format_new_pic(new_pic, ObjectId(user_id), moduleId, _id)).model_dump(), session=session)
                process_thumbnail(new_pic, "restoration")
                photographs_ids.append(result.inserted_id)
            
        return photographs_ids

    def process_changed_pics(self, cursor_change, user_id, mongo, session):       
        #mongo = Mongo()
        try:
            #moduleId = get_module_id("research", mongo)
            #print("cursor_change", cursor_change["changed_pics"])
            if cursor_change.get("changed_pics"):    
                for pic in cursor_change["changed_pics"]:
                    photo_cursor = mongo.connect("photographs").find_one(
                        {"_id": ObjectId(pic["_id"])},
                        session=session
                    )
                    add_delete_to_actual_photo_file_name(photo_cursor["file_name"], "restoration")                
                    store_pic_changes(pic, user_id, mongo, session)                
                    process_thumbnail(pic, "restoration")
                    #if cursor.modified_count > 0:
                        #print(f"Foto actualizada: {pic['_id']}")

        except Exception as e:            
            print(f"Error al procesar fotos cambiadas: {e}") 
            raise e

        

    def patch_request_validation(self, request, _id, restoration_id, mongo):
        #print("request.data", request.data)
        permission = Permission()
        perm = permission.get_permission(request.user)

        if "editar_restauracion" not in perm:
            return Response(
                "You have not permission to approve",
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not self.get_module_id("restoration", mongo):
            return Response(
                {"response": "Módulo no encontrado"}, status=status.HTTP_400_BAD_REQUEST
            )
        # Buscar restauración existente        
        restoration = mongo.connect("restorations").find_one({"_id": ObjectId(restoration_id), "piece_id": ObjectId(_id)})
        if not restoration:
            return Response(
                {"response": "Restauración no encontrada"}, status=status.HTTP_400_BAD_REQUEST
            )

        return restoration
    
    def get_module_id(self, module_name, mongo):
        module = mongo.connect("modules").find_one({"name": module_name})
        return module["_id"]

        
