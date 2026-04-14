from bson import ObjectId
from rest_framework import status
from rest_framework.response import Response

from user_queries.mongo_queries import PIECES_ALL
from user_queries.views.tools import AuditManager

from .base import BaseMovementAPIView, get_movement_document, parse_object_id_list, serialize_mongo


def get_serialized_pieces(mongo):
    if mongo.checkIfExistCollection("pieces_search_serialized"):
        documents = list(
            mongo.connect("pieces_search_serialized")
            .find({"_id": {"$ne": "1code"}, "deleted_at": None})
            .sort("inventory_number", 1)
        )
        return [serialize_mongo(document) for document in documents]

    documents = list(mongo.connect("pieces").aggregate(PIECES_ALL))
    return [serialize_mongo(document) for document in documents]


class MovementSelectPiecesView(BaseMovementAPIView):
    def get(self, request, id):
        mongo = self.get_mongo()
        movement = get_movement_document(mongo, id)

        if not movement:
            return Response(
                {"error": "Movimiento no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        selected_piece_ids = [str(piece_id) for piece_id in movement.get("pieces_ids") or []]

        return Response(
            {
                "movement_id": movement.get("movements_id"),
                "selected_piece_ids": selected_piece_ids,
                "pieces": get_serialized_pieces(mongo),
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, id):
        mongo = self.get_mongo()
        movement = get_movement_document(mongo, id)

        if not movement:
            return Response(
                {"error": "Movimiento no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        selected_piece_ids = parse_object_id_list(request.data.get("piece_ids", []))
        movement_update = {
            "pieces_ids": selected_piece_ids,
            "updated_at": movement.get("updated_at"),
            "updated_by": movement.get("updated_by"),
            "authorized_by_movements": ObjectId(request.user.id),
        }
        movement_update = AuditManager().add_updateInfo(
            movement_update, ObjectId(request.user.id)
        )

        mongo.connect("movements").update_one(
            {"_id": movement["_id"]},
            {"$set": movement_update},
        )

        return Response(
            {
                "movement_id": movement.get("movements_id"),
                "selected_piece_ids": [str(piece_id) for piece_id in selected_piece_ids],
                "message": "Piezas asociadas exitosamente",
            },
            status=status.HTTP_200_OK,
        )
