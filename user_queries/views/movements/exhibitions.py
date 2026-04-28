from datetime import datetime

from bson import ObjectId
from rest_framework import status
from rest_framework.response import Response

from user_queries.shemas.exhibitions_shema import ExhibitionsSchema
from user_queries.views.tools import AuditManager

from .base import (
    BaseMovementAPIView,
    escape_search,
    parse_object_id,
    serialize_mongo,
)


def serialize_catalog_option(document):
    if not document:
        return None

    serialized = serialize_mongo(document)
    serialized["id"] = serialized.get("_id")
    serialized["name"] = (
        serialized.get("name")
        or serialized.get("title")
        or serialized.get("description")
        or ""
    )
    return serialized


def serialize_exhibition(document):
    serialized = serialize_mongo(document)
    serialized["id"] = serialized.get("_id")
    return serialized


def get_institutions_catalog(mongo):
    institutions = list(
        mongo.connect("institutions")
        .find({"deleted_at": None}, {"name": 1})
        .sort("name", 1)
    )
    return [serialize_catalog_option(item) for item in institutions]


def get_contacts_catalog_by_institution(mongo, institution_id):
    if not institution_id:
        return []

    contacts = list(
        mongo.connect("contacts")
        .find(
            {"institution_id": institution_id, "deleted_at": None},
            {"name": 1, "last_name": 1, "institution_id": 1},
        )
        .sort([("name", 1), ("last_name", 1)])
    )

    serialized_contacts = []
    for contact in contacts:
        serialized = serialize_catalog_option(contact)
        serialized["full_name"] = " ".join(
            [part for part in [serialized.get("name"), serialized.get("last_name")] if part]
        ).strip()
        serialized_contacts.append(serialized)

    return serialized_contacts


def build_exhibition_payload(payload):
    return {
        "name": payload.get("name"),
        "institution_id": parse_object_id(payload.get("institution_id")),
        "contact_id": parse_object_id(payload.get("contact_id")),
    }


def validate_exhibition_payload(payload):
    errors = {}

    if not payload.get("name"):
        errors["name"] = "El nombre es un campo requerido"
    if not payload.get("institution_id"):
        errors["institution_id"] = "La institucion es un campo requerido"
    if not payload.get("contact_id"):
        errors["contact_id"] = "El contacto de la institucion es un campo requerido"

    return errors


class ExhibitionsView(BaseMovementAPIView):
    def get(self, request):
        mongo = self.get_mongo()
        search = (request.query_params.get("search") or "").strip()

        query = {"deleted_at": None}
        if search:
            regex = escape_search(search)
            query["$or"] = [
                {"name": regex},
            ]

        exhibitions = list(
            mongo.connect("exhibitions").find(query).sort("name", 1)
        )

        institution_ids = list(
            {
                item.get("institution_id")
                for item in exhibitions
                if item.get("institution_id")
            }
        )
        contact_ids = list(
            {item.get("contact_id") for item in exhibitions if item.get("contact_id")}
        )

        institutions_map = {}
        contacts_map = {}

        if institution_ids:
            institutions_map = {
                str(institution["_id"]): institution.get("name", "")
                for institution in mongo.connect("institutions").find(
                    {"_id": {"$in": institution_ids}},
                    {"name": 1},
                )
            }

        if contact_ids:
            contacts_map = {
                str(contact["_id"]): " ".join(
                    [
                        part
                        for part in [contact.get("name"), contact.get("last_name")]
                        if part
                    ]
                ).strip()
                for contact in mongo.connect("contacts").find(
                    {"_id": {"$in": contact_ids}},
                    {"name": 1, "last_name": 1},
                )
            }

        serialized_exhibitions = []
        for exhibition in exhibitions:
            serialized = serialize_exhibition(exhibition)
            institution_id = serialized.get("institution_id")
            contact_id = serialized.get("contact_id")
            serialized["institution_name"] = (
                institutions_map.get(str(institution_id)) if institution_id else None
            )
            serialized["contact_name"] = (
                contacts_map.get(str(contact_id)) if contact_id else None
            )
            serialized_exhibitions.append(serialized)

        return Response(
            {
                "data": serialized_exhibitions,
                "institutions": get_institutions_catalog(mongo),
                "contacts": [],
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        mongo = self.get_mongo()
        exhibition_data = build_exhibition_payload(request.data)
        errors = validate_exhibition_payload(exhibition_data)

        if errors:
            return Response(
                {"error": "Datos invalidos", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        exhibition_data = AuditManager().add_timestampsInfo(
            exhibition_data, ObjectId(request.user.id)
        )
        exhibition_payload = ExhibitionsSchema(**exhibition_data).model_dump(
            exclude_none=False
        )

        result = mongo.connect("exhibitions").insert_one(exhibition_payload)
        created = mongo.connect("exhibitions").find_one({"_id": result.inserted_id})

        return Response(
            {
                "message": "Exposicion creada exitosamente",
                "exhibition": serialize_exhibition(created),
            },
            status=status.HTTP_201_CREATED,
        )


class ExhibitionDetailView(BaseMovementAPIView):
    def get_exhibition(self, mongo, exhibition_id):
        parsed_id = parse_object_id(exhibition_id)
        if not parsed_id:
            return None

        return mongo.connect("exhibitions").find_one(
            {"_id": parsed_id, "deleted_at": None}
        )

    def get(self, request, id):
        mongo = self.get_mongo()
        exhibition = self.get_exhibition(mongo, id)

        if not exhibition:
            return Response(
                {"error": "Exposicion no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "exhibition": serialize_exhibition(exhibition),
                "institutions": get_institutions_catalog(mongo),
                "contacts": get_contacts_catalog_by_institution(
                    mongo, exhibition.get("institution_id")
                ),
            },
            status=status.HTTP_200_OK,
        )

    def put(self, request, id):
        mongo = self.get_mongo()
        exhibition = self.get_exhibition(mongo, id)

        if not exhibition:
            return Response(
                {"error": "Exposicion no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        exhibition_data = build_exhibition_payload(request.data)
        errors = validate_exhibition_payload(exhibition_data)

        if errors:
            return Response(
                {"error": "Datos invalidos", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        exhibition_data["created_at"] = exhibition.get("created_at")
        exhibition_data["created_by"] = exhibition.get("created_by")
        exhibition_data["updated_at"] = exhibition.get("updated_at")
        exhibition_data["updated_by"] = exhibition.get("updated_by")
        exhibition_data["deleted_at"] = exhibition.get("deleted_at")
        exhibition_data["deleted_by"] = exhibition.get("deleted_by")
        exhibition_data = AuditManager().add_updateInfo(
            exhibition_data, ObjectId(request.user.id)
        )
        exhibition_payload = ExhibitionsSchema(**exhibition_data).model_dump(
            exclude_none=False
        )

        mongo.connect("exhibitions").update_one(
            {"_id": exhibition["_id"]},
            {"$set": exhibition_payload},
        )
        updated = mongo.connect("exhibitions").find_one({"_id": exhibition["_id"]})

        return Response(
            {
                "message": "Exposicion actualizada exitosamente",
                "exhibition": serialize_exhibition(updated),
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, id):
        mongo = self.get_mongo()
        exhibition = self.get_exhibition(mongo, id)

        if not exhibition:
            return Response(
                {"error": "Exposicion no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        mongo.connect("exhibitions").update_one(
            {"_id": exhibition["_id"]},
            {
                "$set": {
                    "deleted_at": datetime.now(AuditManager.tz),
                    "deleted_by": ObjectId(request.user.id),
                }
            },
        )

        return Response(
            {"message": "Exposicion eliminada exitosamente"},
            status=status.HTTP_200_OK,
        )
