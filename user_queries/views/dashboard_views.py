
from bson.decimal128 import Decimal128


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from authentication.custom_jwt import CustomJWTAuthentication
from user_queries.driver_database.mongo import Mongo


class Dashboard(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def get(self, request):
        mongo = Mongo()

        total_value_cursor = mongo.connect("pieces").aggregate([
            { "$match": { "deleted_at": None } },
            {
                "$group": {
                    "_id": None,
                    "total_value": {
                    "$sum": { "$toDouble": "$appraisal" }
                    }
                }            
            }
        ])

        total_value_list = list(total_value_cursor)
        total_value = total_value_list[0]["total_value"] if total_value_list else 0

        data = {
        "pieces": mongo.connect("pieces").count_documents({"deleted_at": None}),
        "research": mongo.connect("researchs").count_documents({"deleted_at": None}),
        "restorations": mongo.connect("restorations").count_documents({"deleted_at": None}),
        "movements": mongo.connect("movements").count_documents({"deleted_at": None}),
        "reports": mongo.connect("reports").count_documents({"deleted_at": None}),
        "users": mongo.connect("authentication_my_user").count_documents({"deleted_at": None}),
        "roles": mongo.connect("roles").count_documents({}),
        "total_value": total_value
            }

        return Response(data, status=status.HTTP_200_OK)