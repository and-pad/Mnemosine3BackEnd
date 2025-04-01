# Librerías estándar

import json
import random
import string
from datetime import datetime
# Librerías de terceros
from bson import ObjectId
from bson.decimal128 import Decimal128
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from time import sleep
# Módulos locales
from user_queries.driver_database.mongo import Mongo
from user_queries.mongo_queries import (
    PIECES_ALL,
    MODULES,
    pieceDetail,
    
)

class UserQueryAll(APIView):
    permission_classes = [IsAuthenticated]
    dbCollection = "pieces"
    dbCollectionPics = "photographs"

    def bson_to_json_serializable(self, doc):
        """Convierte ObjectId, Decimal128 y datetime a tipos serializables."""
        if isinstance(doc, ObjectId):
            return str(doc)  # Convierte ObjectId a string
        elif isinstance(doc, Decimal128):
            return float(doc.to_decimal())  # Convierte Decimal128 a float
        elif isinstance(doc, datetime):
            return doc.isoformat()  # Convierte datetime a formato ISO 8601
        elif isinstance(doc, dict):
            return {
                k: self.bson_to_json_serializable(v) for k, v in doc.items()
            }  # Recorre el diccionario
        elif isinstance(doc, list):
            return [self.bson_to_json_serializable(v) for v in doc]  # Recorre la lista
        else:
            return doc  # Retorna el valor sin cambios si ya es serializable

    def generate_unique_code_version(self, length=120):
        alphabet = string.ascii_letters + string.digits
        return "".join(random.choices(alphabet, k=length))

    def get(self, request, _code):
        mongo = Mongo()
        db = mongo
        time = datetime.now()

        while mongo.checkIfExistCollection("generation_status"):
            sleep(1)

        if not mongo.checkIfExistCollection("pieces_search"):

            db.connect("generation_status").insert_one({"status": "generating"})

            collection = db.connect(self.dbCollection)
            cursor = collection.aggregate(PIECES_ALL)
            db.connect("pieces_search").insert_many(cursor)

        if not mongo.checkIfExistCollection("pieces_search_serialized"):

            db.connect("generation_status").insert_one({"status": "generating"})

            cursor = db.connect("pieces_search").find().sort("inventory_number", 1)
            documents = [self.bson_to_json_serializable(doc) for doc in cursor]
            db.connect("pieces_search_serialized").insert_many(documents)
            db.connect("pieces_search_serialized").insert_one(
                {"_id": "1code", "unique_code": self.generate_unique_code_version()}
            )
        else:
            cursor_code = db.connect("pieces_search_serialized").find_one(
                {"_id": "1code"}
            )
            if cursor_code["unique_code"] == _code:
                return Response(status=status.HTTP_304_NOT_MODIFIED)

        if mongo.checkIfExistCollection("generation_status"):
            db.connect("generation_status").drop()

        serialized_json_data = (
            db.connect("pieces_search_serialized")
            .find({"_id": {"$ne": "1code"}})
            .sort("inventory_number", 1)
        )
        cursor_code = db.connect("pieces_search_serialized").find_one({"_id": "1code"})
        code = cursor_code["unique_code"]
        documents = [
            self.bson_to_json_serializable(doc) for doc in serialized_json_data
        ]
        time_end = datetime.now() - time
        # print(documents[0])

        return Response(
            {"query": documents, "code": code, "query_duration": time_end},
            status=status.HTTP_202_ACCEPTED,
        )


class UserQueryDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, _id):
        if not _id:
            return Response(
                {"error": "Missing _id in request"}, status=status.HTTP_410_GONE
            )
        try:
            object_id = ObjectId(_id)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        mongo = Mongo()
        search_piece = mongo.connect("pieces")

        cursor = search_piece.aggregate(pieceDetail(_id))

        documents = [doc for doc in cursor]
        json_detail = json.loads(json.dumps(documents, default=str))

        modules = mongo.connect("modules")

        cursor = modules.find(MODULES)
        documents = [doc for doc in cursor]
        json_modules = json.loads(json.dumps(documents, default=str))

        if json_detail:
            response_data = {"detail": json_detail, "modules": json_modules}
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Pieces not found"}, status=status.HTTP_404_NOT_FOUND
            )

