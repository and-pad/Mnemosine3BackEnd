from bson import ObjectId
from django.conf import settings
from pymongo import ReplaceOne
from rest_framework import status
from rest_framework.response import Response

from user_queries.mongo_queries import PIECES_ALL
from user_queries.shemas.movements_shema import MovementsSchema
from user_queries.views.tools import AuditManager

from .base import (
    BaseMovementAPIView,
    get_movement_document,
    get_next_movement_id,
    get_internal_institution,
    parse_date,
    parse_object_id,
    parse_object_id_list,
    serialize_mongo,
    serialize_option,
    generation_status_manager,
)


def normalize_piece_list(value):
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def get_piece_label(piece):
    return {
        "_id": str(piece.get("_id")),
        "catalog_number": piece.get("catalog_number"),
        "inventory_number": piece.get("inventory_number"),
    }


class MovementReturnPiecesView(BaseMovementAPIView):
    def get(self, request, id):
        mongo = self.get_mongo()
        movement = get_movement_document(mongo, id)

        if not movement:
            return Response(
                {"error": "Movimiento no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        all_piece_ids = movement.get("pieces_ids") or []
        returned_piece_ids = movement.get("pieces_ids_arrived") or []
        returned_piece_ids_set = {str(piece_id) for piece_id in returned_piece_ids}
        available_piece_ids = [
            str(piece_id)
            for piece_id in all_piece_ids
            if str(piece_id) not in returned_piece_ids_set
        ]

        pieces_map = self.get_pieces_map(mongo, all_piece_ids)
        previous_arrivals = self.serialize_arrival_information(
            movement.get("arrival_information") or [],
            pieces_map,
            self.get_locations_map(mongo),
        )

        internal_institution = get_internal_institution(mongo)
        internal_institution_id = (
            internal_institution.get("_id") if internal_institution else None
        )
        locations = list(
            mongo.connect("exhibitions")
            .find(
                {
                    "institution_id": internal_institution_id,
                    "deleted_at": None,
                },
                {"name": 1, "institution_id": 1},
            )
            .sort("name", 1)
        )

        return Response(
            {
                "movement": self.serialize_movement_summary(movement, mongo),
                "available_piece_ids": available_piece_ids,
                "previous_arrivals": previous_arrivals,
                "locations": [serialize_option(item) for item in locations],
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

        location_id = parse_object_id(request.data.get("location_id"))
        arrival_date = parse_date(request.data.get("arrival_date"))
        piece_ids = parse_object_id_list(request.data.get("piece_ids", []))

        if not location_id:
            return Response(
                {"error": "Indique la ubicación de regreso."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not arrival_date:
            return Response(
                {"error": "Indique la fecha de regreso."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not piece_ids:
            return Response(
                {"error": "Seleccione al menos una pieza para registrar el regreso."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        movement_piece_ids = movement.get("pieces_ids") or []
        valid_piece_ids = {str(piece_id) for piece_id in movement_piece_ids}
        returned_piece_ids = movement.get("pieces_ids_arrived") or []
        returned_piece_ids_set = {str(piece_id) for piece_id in returned_piece_ids}

        requested_piece_ids = []
        seen_piece_ids = set()
        for piece_id in piece_ids:
            piece_id_str = str(piece_id)
            if piece_id_str in seen_piece_ids:
                continue
            seen_piece_ids.add(piece_id_str)
            if piece_id_str not in valid_piece_ids:
                return Response(
                    {"error": "Se enviaron piezas que no pertenecen al movimiento."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if piece_id_str in returned_piece_ids_set:
                return Response(
                    {"error": "Una o más piezas ya habían sido registradas como regresadas."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            requested_piece_ids.append(piece_id)

        arrival_information = movement.get("arrival_information") or []
        arrival_information.append(
            {
                "pieces": requested_piece_ids,
                "location": location_id,
                "arrival_date": arrival_date,
            }
        )

        next_arrived_ids = [*returned_piece_ids, *requested_piece_ids]
        movement_update = {
            "arrival_information": arrival_information,
            "pieces_ids_arrived": next_arrived_ids,
            "arrival_date": arrival_date,
            "arrival_location_id": location_id,
            "type_arrival": "return",
        }
        movement_update = AuditManager().add_updateInfo(
            movement_update, ObjectId(request.user.id)
        )

        mongo.connect("movements").update_one(
            {"_id": movement["_id"]},
            {"$set": movement_update},
        )

        mongo.connect("pieces").update_many(
            {"_id": {"$in": requested_piece_ids}},
            {
                "$set": {
                    "location_id": location_id,
                    "updated_at": movement_update["updated_at"],
                    "updated_by": ObjectId(request.user.id),
                }
            },
        )

        """
        self.update_return_movement(
            mongo,
            original_movement=movement,
            location_id=location_id,
            arrival_date=arrival_date,
            piece_ids=requested_piece_ids,
            user_id=ObjectId(request.user.id),
        )
        """

        #mongo.checkAndDropIfExistCollection("pieces_search")
        pieces = mongo.connect("pieces")
        pieces_search = mongo.connect("pieces_search")
        pipeline = [
            {"$match": {"_id": {"$in": movement.get("pieces_ids") or []}, "deleted_at": None}},
        ] + list(PIECES_ALL)
        cursor = pieces.aggregate(pipeline)
        #print("cursor:", list(cursor))  # Agrega esta línea para imprimir los documentos obtenidos
        operations = []
        for document in cursor:
            print("document_id:", document.get("_id"))  # Agrega esta línea para imprimir el _id de cada documento  
            operations.append(
                ReplaceOne(
                    {"_id": document["_id"]}, document, upsert=True
                )
            )
        print("operations", operations)  # Agrega esta línea para imprimir las operaciones de reemplazo generadas
        if operations:
            pieces_search.bulk_write(operations)

        
        mongo.checkAndDropIfExistCollection("pieces_search_serialized")
        generation_status_manager(mongo)       
        

        return Response(
            {
                "message": f"Se ha registrado el regreso de las piezas seleccionadas en el movimiento {movement.get('movements_id')}",
                "registered_piece_ids": [str(piece_id) for piece_id in requested_piece_ids],
            },
            status=status.HTTP_200_OK,
        )

    def serialize_movement_summary(self, movement, mongo):
        institutions = self.get_named_documents(
            mongo, "institutions", movement.get("institution_ids") or []
        )
        contacts = self.get_named_documents(
            mongo, "contacts", movement.get("contact_ids") or [], include_last_name=True
        )
        exhibition = None
        if movement.get("exhibition_id"):
            exhibition_doc = mongo.connect("exhibitions").find_one(
                {"_id": movement.get("exhibition_id"), "deleted_at": None},
                {"name": 1},
            )
            exhibition = exhibition_doc.get("name") if exhibition_doc else None

        return {
            "id": movement.get("movements_id"),
            "departure_date": movement.get("departure_date").strftime("%Y-%m-%d")
            if movement.get("departure_date")
            else None,
            "exhibition_name": exhibition,
            "institution_names": institutions,
            "contact_names": contacts,
        }

    def get_named_documents(
        self, mongo, collection_name, ids, include_last_name=False
    ):
        object_ids = [item for item in ids if isinstance(item, ObjectId)]
        if not object_ids:
            return []

        projection = {"name": 1}
        if include_last_name:
            projection["last_name"] = 1

        documents = list(
            mongo.connect(collection_name).find(
                {"_id": {"$in": object_ids}, "deleted_at": None}, projection
            )
        )
        documents_by_id = {document["_id"]: document for document in documents}

        result = []
        for object_id in ids:
            document = documents_by_id.get(object_id)
            if not document:
                continue
            if include_last_name:
                result.append(
                    " ".join(
                        part
                        for part in [document.get("name"), document.get("last_name")]
                        if part
                    ).strip()
                )
            else:
                result.append(document.get("name"))
        return result

    def get_pieces_map(self, mongo, piece_ids):
        object_ids = [item for item in piece_ids if isinstance(item, ObjectId)]
        if not object_ids:
            return {}

        documents = list(
            mongo.connect("pieces").find(
                {"_id": {"$in": object_ids}, "deleted_at": None},
                {"catalog_number": 1, "inventory_number": 1},
            )
        )
        return {str(document["_id"]): document for document in documents}

    def get_locations_map(self, mongo):
        locations = list(
            mongo.connect("exhibitions").find(
                {"deleted_at": None},
                {"name": 1},
            )
        )
        return {str(location["_id"]): location.get("name") for location in locations}

    def serialize_arrival_information(self, arrival_information, pieces_map, locations_map):
        serialized = []
        for info in arrival_information:
            piece_ids = normalize_piece_list(info.get("pieces"))
            serialized.append(
                {
                    "location": str(info.get("location")) if info.get("location") else "0",
                    "location_name": locations_map.get(str(info.get("location")), "En préstamo")
                    if info.get("location")
                    else "En préstamo",
                    "arrival_date": info.get("arrival_date").strftime("%Y-%m-%d")
                    if hasattr(info.get("arrival_date"), "strftime")
                    else serialize_mongo(info.get("arrival_date")),
                    "pieces": [
                        get_piece_label(pieces_map[str(piece_id)])
                        for piece_id in piece_ids
                        if str(piece_id) in pieces_map
                    ],
                }
            )
        return serialized

    def update_return_movement(
        self,
        mongo,
        original_movement,
        location_id,
        arrival_date,
        piece_ids,
        user_id,
    ):
        institution = get_internal_institution(mongo)
        venue = mongo.connect("venues").find_one({"name": settings.INSTITUTION_NAME})
        movement_data = {
            #"movements_id": get_next_movement_id(mongo),
            #"movement_type": "internal",
            #"itinerant": False,
            "institution_ids": [institution["_id"]] if institution else [],
            "venues": [venue["_id"]] if venue else [],
            "exhibition_id": location_id,
            #"pieces_ids": piece_ids,
            "pieces_ids_arrived": piece_ids,
            "departure_date": arrival_date,
            "contact_ids": original_movement.get("contact_ids") or [],
            "guard_contact_ids": original_movement.get("guard_contact_ids") or [],
            "authorized_by_movements": user_id,
            "arrival_information": [],
        }

        movement_data = AuditManager().add_timestampsInfo(movement_data, user_id)
        movement = MovementsSchema(**movement_data).model_dump(exclude_none=False)
        mongo.connect("movements").update_one({"_id": original_movement["_id"]}, {"$set": movement})
