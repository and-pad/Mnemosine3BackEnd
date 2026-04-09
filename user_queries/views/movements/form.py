from bson import ObjectId
from rest_framework import status
from rest_framework.response import Response

from user_queries.shemas.movements_shema import MovementsSchema
from user_queries.views.tools import AuditManager

from .base import (
    BaseMovementAPIView,
    get_contacts_by_institutions,
    get_exhibitions_by_institutions,
    get_institutions_payload,
    get_movement_document,
    get_selected_institution_ids,
    get_venues_by_institutions,
    normalize_movement_payload,
    parse_object_id_list,
    serialize_form_movement,
)


class MovementContactsView(BaseMovementAPIView):
    def get(self, request, institution_ids):
        mongo = self.get_mongo()
        parsed_ids = parse_object_id_list(
            [value for value in institution_ids.split(",") if value]
        )
        return Response(
            get_contacts_by_institutions(mongo, parsed_ids),
            status=status.HTTP_200_OK,
        )


class MovementExhibitionsView(BaseMovementAPIView):
    def get(self, request, institution_ids):
        mongo = self.get_mongo()
        parsed_ids = parse_object_id_list(
            [value for value in institution_ids.split(",") if value]
        )
        return Response(
            get_exhibitions_by_institutions(mongo, parsed_ids),
            status=status.HTTP_200_OK,
        )


class MovementVenuesView(BaseMovementAPIView):
    def get(self, request, institution_ids):
        mongo = self.get_mongo()
        parsed_ids = parse_object_id_list(
            [value for value in institution_ids.split(",") if value]
        )
        return Response(
            get_venues_by_institutions(mongo, parsed_ids),
            status=status.HTTP_200_OK,
        )


class MovementsNew(BaseMovementAPIView):
    def get(self, request, id=None):
        mongo = self.get_mongo()
        response_data = get_institutions_payload(mongo)

        if not id:
            response_data["movement"] = None
            response_data["contacts"] = []
            response_data["exhibitions"] = []
            response_data["venues"] = []
            return Response(response_data, status=status.HTTP_200_OK)

        movement = get_movement_document(mongo, id)
        if not movement:
            return Response(
                {"error": "Movimiento no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        internal_institution = response_data.get("internal_institution")
        internal_institution_id = (
            internal_institution.get("_id") if internal_institution else None
        )
        selected_institution_ids = get_selected_institution_ids(
            {
                "movement_type": movement.get("movement_type"),
                "institution_ids": [
                    str(item) for item in movement.get("institution_ids") or []
                ],
                "internal_institution_id": str(internal_institution_id)
                if internal_institution_id
                else None,
            }
        )

        response_data["movement"] = serialize_form_movement(
            movement, internal_institution_id
        )
        response_data["contacts"] = get_contacts_by_institutions(
            mongo, selected_institution_ids
        )
        response_data["exhibitions"] = get_exhibitions_by_institutions(
            mongo, selected_institution_ids
        )
        response_data["venues"] = get_venues_by_institutions(
            mongo, selected_institution_ids
        )
        return Response(response_data, status=status.HTTP_200_OK)

    def post(self, request, id=None):
        mongo = self.get_mongo()
        movement_data = normalize_movement_payload(request.data, mongo)
        movement_data = AuditManager().add_timestampsInfo(
            movement_data, ObjectId(request.user.id)
        )
        movement = MovementsSchema(**movement_data).model_dump(exclude_none=False)
        result = mongo.connect("movements").insert_one(movement)

        return Response(
            {
                "id": movement_data["movements_id"],
                "_id": str(result.inserted_id),
                "movement_id": movement_data["movements_id"],
                "message": "Movimiento creado exitosamente",
            },
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, id):
        mongo = self.get_mongo()
        existing_movement = get_movement_document(mongo, id)

        if not existing_movement:
            return Response(
                {"error": "Movimiento no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        movement_data = normalize_movement_payload(
            {**request.data, "movements_id": existing_movement["movements_id"]},
            mongo,
        )
        movement_data["pieces_ids"] = existing_movement.get("pieces_ids") or []
        movement_data["pieces_ids_arrived"] = (
            existing_movement.get("pieces_ids_arrived") or []
        )
        movement_data["arrival_information"] = (
            existing_movement.get("arrival_information") or []
        )
        movement_data["arrival_date"] = existing_movement.get("arrival_date")
        movement_data["arrival_location_id"] = existing_movement.get(
            "arrival_location_id"
        )
        movement_data["type_arrival"] = existing_movement.get("type_arrival")
        movement_data["authorized_by_movements"] = existing_movement.get(
            "authorized_by_movements"
        )
        movement_data["created_at"] = existing_movement.get("created_at")
        movement_data["created_by"] = existing_movement.get("created_by")
        movement_data["deleted_at"] = existing_movement.get("deleted_at")
        movement_data["deleted_by"] = existing_movement.get("deleted_by")
        movement_data = AuditManager().add_updateInfo(
            movement_data, ObjectId(request.user.id)
        )
        movement = MovementsSchema(**movement_data).model_dump(exclude_none=False)

        mongo.connect("movements").update_one(
            {"_id": existing_movement["_id"]},
            {"$set": movement},
        )

        return Response(
            {
                "id": existing_movement["movements_id"],
                "_id": str(existing_movement["_id"]),
                "movement_id": existing_movement["movements_id"],
                "message": "Movimiento actualizado exitosamente",
            },
            status=status.HTTP_200_OK,
        )
