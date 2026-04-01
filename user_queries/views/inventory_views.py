import json

from bson import ObjectId
from rest_framework import status

# from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

# from user_queries.driver_database import mongo
# from user_queries.views.tools import AuditManager
from rest_framework.views import APIView

from authentication.custom_jwt import CustomJWTAuthentication

# import string
from authentication.views import Permission
from user_queries.driver_database.mongo import Mongo
from user_queries.mongo_queries import (
    PIECES_ALL,
)
from user_queries.shemas.piece_shema import PieceSchema
from user_queries.views.inventory_new_subview import (
    process_get,
    process_post,
    process_put,
)

# from PIL import Image
# from django.conf import settings
from .inventory.edit import InventoryEdit  # no se usa pero es para reexportar la clase

"""
    MODULES,
    pieceDetail,
    inventory_edit,
    research_edit,
"""


class InventoryNew(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def get(self, request):
        mongo = Mongo()
        try:
            response = process_get(mongo)

        except Exception as e:
            return Response(
                {"error": "Can't get the catalogs elements " + str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(response, status=status.HTTP_200_OK)

    def post(self, request):
        """
        Aqui vienen los datos para actualizar el inventario
        primero pasan por una etapa de revision
        si se aprueba se actualiza el inventario eso en put
        si se rechaza se no se hacen los cambios
        los cambios se guardan en la base de datos en la colección inventory_changes_approval
        viene:
        changes, que son los inputs del inventario

        PicsNew, que son los campos y/o argumentos de fotos nuevas
        files[new_img_{x}], que son las fotos nuevas

        DocumentsNew, que son los campos y/o argumentos de documentos nuevos
        files[new_doc_{x}], que son los documentos nuevos

        """

        # Initialize the Mongo connection
        mongo = Mongo()
        changes = process_post(request, mongo)
        print("changes", changes)
        return Response("data saved", status=status.HTTP_200_OK)

    def put(self, request, _id):
        """
        Aqui vienen los datos para actualizar el inventario
        primero pasan por una etapa de revision
        si se aprueba se actualiza el inventario eso en put
        si se rechaza se no se hacen los cambios
        los cambios se guardan en la base de datos en la colección inventory_changes_approval
        viene:

        PicsNew, que son los campos y/o argumentos de fotos nuevas
        files[new_img_{x}], que son las fotos nuevas
        DocumentsNew, que son los campos y/o argumentos de documentos nuevos
        files[new_doc_{x}], que son los documentos nuevos


        """
        permissions = Permission()
        perm = permissions.get_permission(request.user)
        # Ya debe estar filtrado esto en el front end pero por refuerzo de seguridad
        # le buscamos en la base de datos
        if "agregar_inventario" not in perm:
            return Response("Permission denied", status=status.HTTP_403_FORBIDDEN)

        isapproved = request.data.get("isApproved")
        mongo = Mongo()
        print("isapproved", isapproved)
        print("_id", _id)
        if isapproved:
            # Connect to the inventory change approvals collection
            InventoryChanges = mongo.connect("inventory_change_approvals")
            # _id = request.data.get("_id")

            cursor_change = InventoryChanges.find_one(
                {"_id": ObjectId(_id), "approved_rejected": None}
            )
            print("cursor_change", cursor_change)
            if not cursor_change:
                return Response(
                    "No pending changes found", status=status.HTTP_404_NOT_FOUND
                )

            # user_id = request.user.id
            # new_piece = cursor_change.get("new_piece")

            with mongo.start_session() as session:
                try:
                    with session.start_transaction():
                        new_piece_id = process_put(
                            request, mongo, session, cursor_change, _id
                        )
                        # Le agregamos un match al pipeline para traer solo la pieza nueva
                        PIECES_ALL.insert(
                            0, {"$match": {"_id": ObjectId(new_piece_id)}}
                        )
                        piece = mongo.connect("pieces")
                        pieces_search = mongo.connect("pieces_search")
                        cursor = piece.aggregate(PIECES_ALL, session=session)
                        for document in cursor:
                            print("document", document)
                            pieces_search.insert_one(document, session=session)

                        mongo.checkAndDropIfExistCollection("pieces_search_serialized")

                        return Response(
                            "New piece added", status=status.HTTP_201_CREATED
                        )
                except Exception as e:
                    print(f"Error al procesar la aprobación: {e}")
                    raise e

        elif not isapproved:
            with mongo.start_session() as session:
                try:
                    with session.start_transaction():
                        InventoryChanges = mongo.connect(
                            "inventory_change_approvals"
                        ).find_one_and_update(
                            {"_id": ObjectId(_id), "approved_rejected": None},
                            {
                                "$set": {
                                    "approved_rejected": "rejected",
                                    "approved_rejected_by": ObjectId(request.user.id),
                                }
                            },
                            session=session,
                        )

                        return Response("Change rejected", status=status.HTTP_200_OK)
                except Exception as e:
                    print(f"Error al procesar el rechazo: {e}")
                    raise e

        return Response("Missing parameters", status=status.HTTP_501_NOT_IMPLEMENTED)


class InventoryPending(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def get(self, request):
        mongo = Mongo()
        try:
            response_data = list(
                mongo.connect("inventory_change_approvals").find(
                    {
                        "approved_rejected": {"$exists": True, "$eq": None},
                        "new_piece": {"$exists": True},
                    }
                )
            )
            response_data = json.loads(json.dumps(response_data, default=str))
            print("response_data", response_data)

        except Exception as e:
            return Response(
                {"error": "Can't get the catalogs elements " + str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(response_data, status=status.HTTP_200_OK)
