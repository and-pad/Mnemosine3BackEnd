from bson import ObjectId
import json

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


from user_queries.driver_database.mongo import Mongo

from rest_framework.permissions import IsAuthenticated
from .tools import AuditManager
from authentication.views import Permission
from restorations.request_data_handler import load_request_data


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

    def get(self, request, _id):
        mongo = Mongo()

        restorations_cursor = mongo.connect("restorations").aggregate(
            restorations_select(_id)
        )
        restorations = list(restorations_cursor)
        print("restorations", restorations)
        # restorations_photos = mongo.connect("restorations_photos").find({"restoration_id": {"$in": [ObjectId(restoration["_id"]) for #restoration in restorations]}})

        restorations_json = json.loads(json.dumps(restorations, default=str))

        return Response({"restorations": restorations_json}, status=status.HTTP_200_OK)


class RestorationEdit(APIView):
    permission_classes = [IsAuthenticated]

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
        print("photos", photos)

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
        print("documents", documents)
        
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

        documents 

        
        return 


    def patch_request_validation(self, request, _id, restoration_id, mongo):
        print("request.data", request.data)
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

        
