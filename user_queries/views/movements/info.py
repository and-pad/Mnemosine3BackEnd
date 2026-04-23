from datetime import datetime

from bson import Decimal128, ObjectId
from rest_framework import status
from rest_framework.response import Response

from user_queries.mongo_queries import PIECES_ALL
from user_queries.shemas.prorogations_shema import ProrogationsSchema
from user_queries.views.tools import AuditManager
from pymongo import ReplaceOne
from time import sleep
import string
import random


from .base import (
    BaseMovementAPIView,
    get_movement_document,
    parse_date,
    serialize_mongo,
    generation_status_manager,
)


def format_user_name(user):
    if not user:
        return None

    full_name = " ".join(
        part for part in [user.get("name"), user.get("last_name")] if part
    ).strip()
    return full_name or user.get("email") or user.get("username") or None


def get_option_map(mongo, collection_name, ids):
    object_ids = [value for value in ids if isinstance(value, ObjectId)]
    if not object_ids:
        return {}

    return {
        item["_id"]: serialize_mongo(item)
        for item in mongo.connect(collection_name).find(
            {"_id": {"$in": object_ids}, "deleted_at": None}
        )
    }
"""
def generate_unique_code_version(length=120):
        alphabet = string.ascii_letters + string.digits
        return "".join(random.choices(alphabet, k=length))
"""
"""
def bson_to_json_serializable(doc):
       
        if isinstance(doc, ObjectId):
            return str(doc)  # Convierte ObjectId a string
        elif isinstance(doc, Decimal128):
            return float(doc.to_decimal())  # Convierte Decimal128 a float
        elif isinstance(doc, datetime):
            return doc.isoformat()  # Convierte datetime a formato ISO 8601
        elif isinstance(doc, dict):
            return {
                k: bson_to_json_serializable(v) for k, v in doc.items()
            }  # Recorre el diccionario
        elif isinstance(doc, list):
            return [bson_to_json_serializable(v) for v in doc]  # Recorre la lista
        else:
            return doc  # Retorna el valor sin cambios si ya es serializable
"""
def get_selected_pieces_info(mongo, piece_ids):
    if not piece_ids:
        return []

    
    while mongo.checkIfExistCollection("generation_status"):
        sleep(1)
    
    generation_status_manager(mongo)   

    unique_piece_ids = []
    seen_piece_ids = set()
    for piece_id in piece_ids:
        piece_id_str = str(piece_id)
        if piece_id_str in seen_piece_ids:
            continue
        seen_piece_ids.add(piece_id_str)
        unique_piece_ids.append(piece_id_str)

    documents = list(
        mongo.connect("pieces_search_serialized").find(
            {"_id": {"$in": unique_piece_ids}, "deleted_at": None}
        )
    )

    piece_map = {str(piece.get("_id")): serialize_mongo(piece) for piece in documents}
    return [piece_map[str(piece_id)] for piece_id in piece_ids if str(piece_id) in piece_map]


def build_piece_map(mongo, piece_ids):
    pieces = get_selected_pieces_info(mongo, piece_ids)
    return {str(piece.get("_id")): piece for piece in pieces if piece.get("_id")}


def get_ordered_pieces(piece_map, piece_ids):
    return [piece_map[str(piece_id)] for piece_id in piece_ids if str(piece_id) in piece_map]


def serialize_prorogation(document, pieces):
    return {
        "id": str(document.get("_id")),
        "new_arrival_date": document.get("new_arrival_date").strftime("%Y-%m-%d")
        if document.get("new_arrival_date")
        else None,
        "new_start_exhibition_date": document.get(
            "new_start_exhibition_date"
        ).strftime("%Y-%m-%d")
        if document.get("new_start_exhibition_date")
        else None,
        "new_end_exhibition_date": document.get(
            "new_end_exhibition_date"
        ).strftime("%Y-%m-%d")
        if document.get("new_end_exhibition_date")
        else None,
        "pieces": pieces,
    }


class MovementInfoView(BaseMovementAPIView):
    def get(self, request, id):
        mongo = self.get_mongo()
        movement = get_movement_document(mongo, id)

        if not movement:
            return Response(
                {"error": "Movimiento no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        institution_map = get_option_map(
            mongo, "institutions", movement.get("institution_ids") or []
        )
        contact_ids = (movement.get("contact_ids") or []) + (
            movement.get("guard_contact_ids") or []
        )
        contact_map = get_option_map(mongo, "contacts", contact_ids)
        exhibition_map = get_option_map(
            mongo,
            "exhibitions",
            [movement.get("exhibition_id")] if movement.get("exhibition_id") else [],
        )
        venue_map = get_option_map(mongo, "venues", movement.get("venues") or [])

        authorized_by = None
        if movement.get("authorized_by_movements"):
            authorized_by = mongo.connect("authentication_my_user").find_one(
                {"_id": movement.get("authorized_by_movements")}
            )

        prorogation_documents = list(
            mongo.connect("prorogations").find(
                {"movement_id": movement["_id"], "deleted_at": None}
            )
        )

        movement_piece_ids = movement.get("pieces_ids") or []
        returned_piece_ids = movement.get("pieces_ids_arrived") or []
        prorogation_piece_ids_map = {
            str(prorogation.get("_id")): prorogation.get("pieces_ids") or []
            for prorogation in prorogation_documents
        }
        all_piece_ids = [
            *movement_piece_ids,
            *returned_piece_ids,
            *[
                piece_id
                for piece_ids in prorogation_piece_ids_map.values()
                for piece_id in piece_ids
            ],
        ]

        piece_map = build_piece_map(mongo, all_piece_ids)
        pieces = get_ordered_pieces(piece_map, movement_piece_ids)
        returned_pieces = get_ordered_pieces(piece_map, returned_piece_ids)

        inventory_id = self.get_module_inventory_id(mongo)
        photos_by_piece_id = self.get_pieces_photos_grouped(
            mongo, all_piece_ids, inventory_id
        )
        photos = self.flatten_pieces_photos(photos_by_piece_id, movement_piece_ids)
        returned_photos = self.flatten_pieces_photos(
            photos_by_piece_id, returned_piece_ids
        )

        prorogations = []
        for prorogation in prorogation_documents:
            prorogation_id = str(prorogation.get("_id"))
            prorogation_piece_ids = prorogation_piece_ids_map.get(prorogation_id, [])
            prorogation_pieces = get_ordered_pieces(piece_map, prorogation_piece_ids)
            prorogations.append(
                {
                    **serialize_prorogation(prorogation, prorogation_pieces),
                    "photos": self.flatten_pieces_photos(
                        photos_by_piece_id, prorogation_piece_ids
                    ),
                }
            )

        response_data = {
            "movement": {
                "id": int(movement.get("movements_id")),
                "_id": str(movement.get("_id")),
                "movement_type": movement.get("movement_type"),
                "itinerant": bool(movement.get("itinerant")),
                "departure_date": movement.get("departure_date").strftime("%Y-%m-%d")
                if movement.get("departure_date")
                else None,
                "start_exposure": movement.get("start_exposure").strftime("%Y-%m-%d")
                if movement.get("start_exposure")
                else None,
                "end_exposure": movement.get("end_exposure").strftime("%Y-%m-%d")
                if movement.get("end_exposure")
                else None,
                "observations": movement.get("observations") or "",
                "authorized_by_movements": str(movement.get("authorized_by_movements"))
                if movement.get("authorized_by_movements")
                else None,
                "authorized_by_name": format_user_name(authorized_by),
                "institutions": [
                    institution_map[institution_id]
                    for institution_id in movement.get("institution_ids") or []
                    if institution_id in institution_map
                ],
                "contacts": [
                    contact_map[contact_id]
                    for contact_id in movement.get("contact_ids") or []
                    if contact_id in contact_map
                ],
                "guard_contacts": [
                    contact_map[contact_id]
                    for contact_id in movement.get("guard_contact_ids") or []
                    if contact_id in contact_map
                ],
                "exhibition": exhibition_map.get(movement.get("exhibition_id")),
                "venues": [
                    venue_map[venue_id]
                    for venue_id in movement.get("venues") or []
                    if venue_id in venue_map
                ],
            },
            "pieces": pieces,
            "photos": photos,
            "returned_pieces": returned_pieces,
            "returned_photos": returned_photos,
            "prorogations": prorogations,
        }

        return Response(response_data, status=status.HTTP_200_OK)
    
    def get_module_inventory_id(self, mongo):
        module_id = mongo.connect("modules").find_one({"name": "inventory"}, {"_id": 1})        
        if module_id:
            return module_id["_id"]
        return None

    def get_pieces_photos_grouped(self, mongo, piece_ids, inventory_id):
        if not piece_ids or not inventory_id:
            return {}

        unique_piece_ids = []
        seen_piece_ids = set()
        for piece_id in piece_ids:
            if not isinstance(piece_id, ObjectId):
                continue
            piece_id_str = str(piece_id)
            if piece_id_str in seen_piece_ids:
                continue
            seen_piece_ids.add(piece_id_str)
            unique_piece_ids.append(piece_id)

        photos = list(
            mongo.connect("photographs")
            .find(
                {
                    "piece_id": {"$in": unique_piece_ids},
                    "deleted_at": None,
                    "module_id": inventory_id,
                },
                {
                    "_id": 1,
                    "file_name": 1,
                    "size": 1,
                    "mime_type": 1,
                    "piece_id": 1,
                    "description": 1,
                    "photographer": 1,
                    "photographed_at": 1,
                    "main_photography": 1,
                },
            )
            .sort([("piece_id", 1), ("main_photography", -1), ("_id", 1)])
        )

        photos_by_piece_id = {}
        for photo in photos:
            serialized_photo = serialize_mongo(photo)
            piece_id = serialized_photo.get("piece_id")
            if not piece_id:
                continue
            photos_by_piece_id.setdefault(str(piece_id), []).append(serialized_photo)

        return photos_by_piece_id

    def flatten_pieces_photos(self, photos_by_piece_id, piece_ids):
        photos = []
        seen_piece_ids = set()

        for piece_id in piece_ids:
            piece_id_str = str(piece_id)
            if piece_id_str in seen_piece_ids:
                continue
            seen_piece_ids.add(piece_id_str)
            photos.extend(photos_by_piece_id.get(piece_id_str, []))

        return photos

class MovementAuthorizeView(BaseMovementAPIView):
    def post(self, request, id):
        mongo = self.get_mongo()
        with mongo.start_session() as session:
            try:
                with session.start_transaction():
                    movement = mongo.connect("movements").find_one(
                        {"movements_id": int(id), "deleted_at": None},
                        session=session,
                    )

                    if not movement:
                        return Response(
                            {"error": "Movimiento no encontrado"},
                            status=status.HTTP_404_NOT_FOUND,
                        )

                    if movement.get("authorized_by_movements"):
                        return Response(
                            {"error": "El movimiento ya fue autorizado"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    if not movement.get("pieces_ids"):
                        return Response(
                            {"error": "El movimiento no tiene piezas asociadas"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    movement_update = {
                        "authorized_by_movements": ObjectId(request.user.id),
                    }
                    movement_update = AuditManager().add_updateInfo(
                        movement_update, ObjectId(request.user.id)
                    )

                    mongo.connect("movements").update_one(
                        {"_id": movement["_id"]},
                        {"$set": movement_update},
                        session=session,
                    )

                    pieces = mongo.connect("pieces")

                    cursor_pieces = pieces.update_many(
                        {"_id": {"$in": movement["pieces_ids"]}},
                        {"$set": {"location_id": None}},
                        session=session,
                    )

                    if cursor_pieces.modified_count > 0:
                        pieces_search = mongo.connect("pieces_search")

                        pipeline = [
                            {"$match": {"_id": {"$in": movement["pieces_ids"]}}}
                        ] + list(PIECES_ALL)
                        cursor = pieces.aggregate(pipeline, session=session)

                        operations = []

                        for document in cursor:
                            operations.append(
                                ReplaceOne(
                                    {"_id": document["_id"]}, document, upsert=True
                                )
                            )

                        if operations:
                            pieces_search.bulk_write(operations, session=session)

                        mongo.checkAndDropIfExistCollection("pieces_search_serialized")
            except Exception as e:
                print(f"Error al autorizar movimiento: {e}")
                raise

        return Response(
            {"message": "Movimiento autorizado exitosamente"},
            status=status.HTTP_200_OK,
        )


class MovementRejectView(BaseMovementAPIView):
    def post(self, request, id):
        mongo = self.get_mongo()
        movement = get_movement_document(mongo, id)

        if not movement:
            return Response(
                {"error": "Movimiento no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        now = datetime.now(AuditManager.tz)
        mongo.connect("movements").update_one(
            {"_id": movement["_id"]},
            {
                "$set": {
                    "deleted_at": now,
                    "deleted_by": ObjectId(request.user.id),
                    "updated_at": now,
                    "updated_by": ObjectId(request.user.id),
                }
            },
        )

        return Response(
            {"message": "Movimiento rechazado exitosamente"},
            status=status.HTTP_200_OK,
        )


class MovementProrogationUpdateView(BaseMovementAPIView):
    def put(self, request, id):
        if not ObjectId.is_valid(id):
            return Response(
                {"error": "Prórroga no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        mongo = self.get_mongo()
        prorogation = mongo.connect("prorogations").find_one(
            {"_id": ObjectId(id), "deleted_at": None}
        )

        if not prorogation:
            return Response(
                {"error": "Prórroga no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        update_data = {
            "movement_id": prorogation.get("movement_id"),
            "pieces_ids": prorogation.get("pieces_ids") or [],
            "new_arrival_date": parse_date(request.data.get("new_arrival_date"))
            or prorogation.get("new_arrival_date"),
            "new_start_exhibition_date": parse_date(
                request.data.get("new_start_exhibition_date")
            )
            or prorogation.get("new_start_exhibition_date"),
            "new_end_exhibition_date": parse_date(
                request.data.get("new_end_exhibition_date")
            )
            or prorogation.get("new_end_exhibition_date"),
            "created_at": prorogation.get("created_at"),
            "created_by": prorogation.get("created_by"),
            "deleted_at": prorogation.get("deleted_at"),
            "deleted_by": prorogation.get("deleted_by"),
        }
        update_data = AuditManager().add_updateInfo(update_data, ObjectId(request.user.id))
        update_data = ProrogationsSchema(**update_data).model_dump(exclude_none=True)

        mongo.connect("prorogations").update_one(
            {"_id": prorogation["_id"]},
            {"$set": update_data},
        )

        updated_document = mongo.connect("prorogations").find_one({"_id": prorogation["_id"]})
        pieces = get_selected_pieces_info(mongo, updated_document.get("pieces_ids") or [])

        return Response(
            {
                "message": "Prórroga actualizada exitosamente",
                "prorogation": serialize_prorogation(updated_document, pieces),
            },
            status=status.HTTP_200_OK,
        )
