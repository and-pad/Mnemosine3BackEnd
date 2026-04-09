import json
import re
from datetime import datetime

from bson import ObjectId
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from authentication.custom_jwt import CustomJWTAuthentication
from user_queries.driver_database.mongo import Mongo


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
    movement_doc = mongo.connect("movements").find_one(
        {},
        sort=[("movements_id", -1)],
        projection={"movements_id": 1},
    )
    return int(movement_doc.get("movements_id", 0)) + 1 if movement_doc else 1


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
