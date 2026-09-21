import json
import random
import re
from datetime import datetime
import string
from pymongo import ReturnDocument

from bson import Decimal128, ObjectId
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from authentication.custom_jwt import CustomJWTAuthentication
from authentication.views import Permission
from user_queries.driver_database.mongo import Mongo

MOVEMENT_PERMISSIONS = {
    "view": "ver_movimientos",
    "create": "agregar_movimientos",
    "edit": "editar_movimientos",
    "delete": "eliminar_movimientos",
    "authorize": "autorizar_movimientos",
}


def ensure_movements_indexes(mongo):
    """Validate movement identifiers and create the persistent unique index."""
    collection = mongo.connect("movements")
    duplicates = list(
        collection.aggregate([
            {"$group": {"_id": "$movements_id", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 1}}},
        ])
    )
    if duplicates:
        raise RuntimeError(f"No se puede crear el índice: movements_id duplicados {duplicates}")

    for document in collection.find({}, {"movements_id": 1}):
        value = document.get("movements_id")
        if not isinstance(value, int) or isinstance(value, bool):
            raise RuntimeError(
                "No se puede crear el índice: todos los movimientos requieren "
                f"movements_id entero (documento {document.get('_id')!s})"
            )

    indexes = list(collection.list_indexes())
    target = next((index for index in indexes if index.get("name") == "movements_id_1"), None)
    expected_key = [("movements_id", 1)]
    if target:
        if list(target.get("key", {}).items()) != expected_key or target.get("unique") is not True:
            raise RuntimeError("El índice movements_id_1 existe con una configuración incompatible")
        return target["name"]

    equivalent = next(
        (
            index for index in indexes
            if list(index.get("key", {}).items()) == expected_key and index.get("unique") is True
        ),
        None,
    )
    if equivalent:
        return equivalent["name"]
    return collection.create_index(expected_key, unique=True, name="movements_id_1")

def bson_to_json_serializable(doc):
        """Convierte ObjectId, Decimal128 y datetime a tipos serializables."""
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
        
def generate_unique_code_version(length=120):
        alphabet = string.ascii_letters + string.digits
        return "".join(random.choices(alphabet, k=length))

def generation_status_manager(mongo):
    db = mongo   
    if not mongo.checkIfExistCollection("pieces_search_serialized"):       
        try: 
            db.connect("generation_status").insert_one({"status": "generating"})
            cursor = db.connect("pieces_search").find().sort("inventory_number", 1)
            documents = [bson_to_json_serializable(doc) for doc in cursor]
            db.connect("pieces_search_serialized").insert_many(documents)

            new_code = generate_unique_code_version()
            db.connect("pieces_search_serialized").insert_one(
                {"_id": "1code", "unique_code": new_code}
            )
            
            db.checkAndDropIfExistCollection("generation_status")

        except Exception as e:
            db.checkAndDropIfExistCollection("generation_status")
            raise e

def parse_object_id(value):
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


def parse_object_id_list(values):
    if not isinstance(values, list):
        return []
    return [
        object_id
        for object_id in (parse_object_id(value) for value in values)
        if object_id
    ]


def parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return False


def parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return None
    return None


def serialize_mongo(document):
    return json.loads(json.dumps(document, default=str))


def serialize_option(document):
    serialized = serialize_mongo(document)
    serialized["id"] = serialized.get("_id")
    return serialized


def get_internal_institution(mongo):
    return mongo.connect("institutions").find_one(
        {"name": settings.INSTITUTION_NAME, "deleted_at": None}
    )


def get_next_movement_id(mongo):
    """Return a unique movement number from Mongo's atomic counter."""
    movement_doc = mongo.connect("movements").find_one(
        {},
        sort=[("movements_id", -1)],
        projection={"movements_id": 1},
    )
    historical_max = int(movement_doc.get("movements_id", 0)) if movement_doc else 0
    counters = mongo.connect("counters")
    counters.find_one_and_update(
        {"_id": "movements_id"},
        {"$setOnInsert": {"seq": historical_max}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    # Keep a pre-existing counter ahead of any historical records discovered
    # during deployment/recovery, without replacing the atomic increment.
    counters.find_one_and_update(
        {"_id": "movements_id"},
        {"$max": {"seq": historical_max}},
        return_document=ReturnDocument.AFTER,
    )
    counter = counters.find_one_and_update(
        {"_id": "movements_id"},
        {"$inc": {"seq": 1}},
        return_document=ReturnDocument.AFTER,
    )
    if not counter or not isinstance(counter.get("seq"), int):
        raise RuntimeError("No fue posible obtener el contador de movimientos")
    return counter["seq"]


def get_institutions_payload(mongo):
    institutions = list(
        mongo.connect("institutions")
        .find({"deleted_at": None}, {"name": 1})
        .sort("name", 1)
    )
    internal_institution = get_internal_institution(mongo)
    return {
        "institutions": [serialize_option(item) for item in institutions],
        "internal_institution": serialize_option(internal_institution)
        if internal_institution
        else None,
    }


def get_selected_institution_ids(payload):
    movement_type = payload.get("movement_type")
    if movement_type == "internal":
        internal_id = parse_object_id(payload.get("internal_institution_id"))
        return [internal_id] if internal_id else []
    return parse_object_id_list(payload.get("institution_ids", []))


def get_contacts_by_institutions(mongo, institution_ids):
    if not institution_ids:
        return []
    contacts = list(
        mongo.connect("contacts")
        .find(
            {"institution_id": {"$in": institution_ids}, "deleted_at": None},
            {"name": 1, "last_name": 1, "institution_id": 1},
        )
        .sort([("name", 1), ("last_name", 1)])
    )
    return [serialize_option(item) for item in contacts]


def get_exhibitions_by_institutions(mongo, institution_ids):
    if not institution_ids:
        return []
    exhibitions = list(
        mongo.connect("exhibitions")
        .find(
            {"institution_id": {"$in": institution_ids}, "deleted_at": None},
            {"name": 1, "institution_id": 1},
        )
        .sort("name", 1)
    )
    return [serialize_option(item) for item in exhibitions]


def get_venues_by_institutions(mongo, institution_ids):
    if not institution_ids:
        return []
    venues = list(
        mongo.connect("venues")
        .find(
            {"institution_id": {"$in": institution_ids}, "deleted_at": None},
            {"name": 1, "institution_id": 1},
        )
        .sort("name", 1)
    )
    return [serialize_option(item) for item in venues]


def normalize_movement_payload(payload, mongo):
    selected_institutions = get_selected_institution_ids(payload)
    movement_type = payload.get("movement_type") or "external"
    itinerant = movement_type == "external" and parse_bool(payload.get("itinerant"))

    movement_data = {
        "movements_id": int(payload.get("movements_id") or 0)
        or get_next_movement_id(mongo),
        "movement_type": movement_type,
        "itinerant": itinerant,
        "institution_ids": selected_institutions if movement_type != "internal" else [],
        "contact_ids": parse_object_id_list(payload.get("contact_ids", [])),
        "guard_contact_ids": parse_object_id_list(payload.get("guard_contact_ids", [])),
        "exhibition_id": parse_object_id(payload.get("exhibition_id")),
        "venues": []
        if movement_type == "internal"
        else parse_object_id_list(payload.get("venues", [])),
        "departure_date": parse_date(payload.get("departure_date")),
        "arrival_date": None,
        "observations": payload.get("observations") or None,
        "start_exposure": None,
        "end_exposure": None,
        "pieces_ids": [],
        "authorized_by_movements": None,
        "arrival_location_id": None,
        "type_arrival": None,
        "pieces_ids_arrived": [],
        "arrival_information": [],
    }

    if movement_type != "restoration":
        movement_data["start_exposure"] = parse_date(payload.get("start_exposure"))
        movement_data["end_exposure"] = parse_date(payload.get("end_exposure"))

    if movement_type == "internal":
        internal_id = parse_object_id(payload.get("internal_institution_id"))
        if internal_id:
            movement_data["institution_ids"] = [internal_id]

    return movement_data


def serialize_form_movement(document, internal_institution_id=None):
    if not document:
        return None

    return {
        "id": str(document.get("movements_id") or document.get("_id")),
        "_id": str(document.get("_id")),
        "movements_id": int(document.get("movements_id", 0)),
        "movement_type": document.get("movement_type") or "external",
        "itinerant": bool(document.get("itinerant")),
        "institution_ids": [
            str(item) for item in document.get("institution_ids") or []
        ],
        "internal_institution_id": str(
            internal_institution_id
            or (document.get("institution_ids") or [None])[0]
            or ""
        ),
        "contact_ids": [str(item) for item in document.get("contact_ids") or []],
        "guard_contact_ids": [
            str(item) for item in document.get("guard_contact_ids") or []
        ],
        "exhibition_id": str(document.get("exhibition_id"))
        if document.get("exhibition_id")
        else None,
        "venues": [str(item) for item in document.get("venues") or []],
        "departure_date": document.get("departure_date").strftime("%Y-%m-%d")
        if document.get("departure_date")
        else None,
        "start_exposure": document.get("start_exposure").strftime("%Y-%m-%d")
        if document.get("start_exposure")
        else None,
        "end_exposure": document.get("end_exposure").strftime("%Y-%m-%d")
        if document.get("end_exposure")
        else None,
        "observations": document.get("observations") or "",
        "paso2": True,
    }


def get_movement_document(mongo, movement_id):
    return mongo.connect("movements").find_one(
        {"movements_id": int(movement_id), "deleted_at": None}
    )


def escape_search(search):
    return {"$regex": f"{re.escape(search)}", "$options": "i"} if search else None


class BaseMovementAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def get_mongo(self):
        return Mongo()

    def get_request_permissions(self, request):
        permissions = Permission()
        return permissions.get_permission(request.user)

    def has_permission(self, request, permission):
        return permission in self.get_request_permissions(request)

    def has_any_permission(self, request, permissions):
        request_permissions = self.get_request_permissions(request)
        return any(permission in request_permissions for permission in permissions)

    def deny_permission(self, message="No tienes permisos para ejecutar esta acción."):
        return Response(
            {
                "ok": False,
                "message": message,
                "detail": message,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
