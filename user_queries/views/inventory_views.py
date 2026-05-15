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

    def get_request_permissions(self, request):
        permissions = Permission()
        return permissions.get_permission(request.user)

    def deny_permission(self, message):
        return Response(message, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        if "agregar_inventario" not in self.get_request_permissions(request):
            return self.deny_permission("No tienes permiso para agregar inventario")

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
        if "agregar_inventario" not in self.get_request_permissions(request):
            return self.deny_permission("No tienes permiso para agregar inventario")

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
        if "autorizar_colecciones" not in self.get_request_permissions(request):
            return self.deny_permission("No tienes permiso para autorizar cambios de inventario")

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
                        pipeline = [
                            {"$match": {"_id": ObjectId(new_piece_id)}}
                        ] + list(PIECES_ALL)
                        piece = mongo.connect("pieces")
                        pieces_search = mongo.connect("pieces_search")
                        cursor = piece.aggregate(pipeline, session=session)
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

    def get_request_permissions(self, request):
        permissions = Permission()
        return permissions.get_permission(request.user)

    def _serialize(self, document):
        return json.loads(json.dumps(document, default=str))

    def _get_user_map(self, mongo, user_ids):
        valid_ids = [user_id for user_id in user_ids if isinstance(user_id, ObjectId)]
        if not valid_ids:
            return {}

        users = list(
            mongo.connect("authentication_my_user").find(
                {"_id": {"$in": valid_ids}},
                {"username": 1, "email": 1},
            )
        )
        return {
            user["_id"]: {
                "_id": str(user["_id"]),
                "username": user.get("username") or "Usuario desconocido",
                "email": user.get("email") or "",
            }
            for user in users
        }

    def _enrich_pending_items(self, items, mongo):
        user_ids = [
            item.get("created_by")
            for item in items
            if isinstance(item.get("created_by"), ObjectId)
        ]
        piece_ids = [
            item.get("piece_id")
            for item in items
            if isinstance(item.get("piece_id"), ObjectId)
        ]

        user_map = self._get_user_map(mongo, user_ids)
        piece_map = {}
        if piece_ids:
            pieces = list(
                mongo.connect("pieces_search").find(
                    {"_id": {"$in": piece_ids}},
                    {
                        "inventory_number": 1,
                        "catalog_number": 1,
                        "origin_number": 1,
                        "description_inventory": 1,
                    },
                )
            )
            piece_map = {piece["_id"]: piece for piece in pieces}

        enriched = []
        for item in items:
            serialized = self._serialize(item)
            created_by = item.get("created_by")
            piece_id = item.get("piece_id")

            serialized["created_by_info"] = user_map.get(created_by)
            if isinstance(piece_id, ObjectId):
                serialized["piece_info"] = self._serialize(piece_map.get(piece_id))
            else:
                serialized["piece_info"] = None
            enriched.append(serialized)

        return enriched

    def get(self, request):
        if "autorizar_colecciones" not in self.get_request_permissions(request):
            return Response(
                "No tienes permiso para ver pendientes de inventario",
                status=status.HTTP_400_BAD_REQUEST,
            )

        mongo = Mongo()
        try:
            pending_items = list(
                mongo.connect("inventory_change_approvals").find(
                    {"approved_rejected": {"$exists": True, "$eq": None}}
                )
            )

            new_pieces = [
                item for item in pending_items if "new_piece" in item
            ]
            modified_pieces = [
                item for item in pending_items if "new_piece" not in item
            ]

            response_data = {
                "new_pieces": self._enrich_pending_items(new_pieces, mongo),
                "modified_pieces": self._enrich_pending_items(modified_pieces, mongo),
            }

        except Exception as e:
            return Response(
                {"error": "Can't get the catalogs elements " + str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(response_data, status=status.HTTP_200_OK)
