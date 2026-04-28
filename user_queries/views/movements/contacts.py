from datetime import datetime

from bson import ObjectId
from rest_framework import status
from rest_framework.response import Response

from user_queries.shemas.contacts_shema import ContactsSchema
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


def serialize_contact(document):
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


def get_treatment_titles_catalog(mongo):
    treatment_catalog = mongo.connect("catalogs").find_one(
        {"code": "treatment", "deleted_at": None},
        {"_id": 1},
    )
    if not treatment_catalog:
        return []

    titles = list(
        mongo.connect("catalog_elements")
        .find(
            {
                "catalog_id": treatment_catalog["_id"],
                "deleted_at": None,
            },
            {"title": 1},
        )
        .sort("title", 1)
    )
    return [serialize_catalog_option(item) for item in titles]


def build_contact_payload(payload):
    return {
        "name": payload.get("name"),
        "last_name": payload.get("last_name"),
        "m_last_name": payload.get("m_last_name"),
        "treatment_title": parse_object_id(payload.get("treatment_title")),
        "position": payload.get("position"),
        "departament": payload.get("departament"),
        "phone": payload.get("phone"),
        "phone2": payload.get("phone2"),
        "email": payload.get("email"),
        "institution_id": parse_object_id(payload.get("institution_id")),
    }


def validate_contact_payload(payload):
    errors = {}

    if not payload.get("name"):
        errors["name"] = "El nombre es un campo requerido"
    if not payload.get("last_name"):
        errors["last_name"] = "El apellido paterno es un campo requerido"
    if not payload.get("email"):
        errors["email"] = "El correo es un campo requerido"
    elif isinstance(payload["email"], str) and "@" not in payload["email"]:
        errors["email"] = "El correo no es valido"
    if not payload.get("institution_id"):
        errors["institution_id"] = "La institucion es un campo requerido"

    return errors


class ContactsView(BaseMovementAPIView):
    def get(self, request):
        mongo = self.get_mongo()
        search = (request.query_params.get("search") or "").strip()

        query = {"deleted_at": None}
        if search:
            regex = escape_search(search)
            query["$or"] = [
                {"name": regex},
                {"last_name": regex},
                {"m_last_name": regex},
                {"phone": regex},
                {"email": regex},
                {"position": regex},
                {"departament": regex},
            ]

        contacts = list(mongo.connect("contacts").find(query).sort("name", 1))

        institution_ids = list(
            {item.get("institution_id") for item in contacts if item.get("institution_id")}
        )
        institutions_map = {}
        if institution_ids:
            institutions_map = {
                str(institution["_id"]): institution.get("name", "")
                for institution in mongo.connect("institutions").find(
                    {"_id": {"$in": institution_ids}},
                    {"name": 1},
                )
            }

        serialized_contacts = []
        for contact in contacts:
            serialized = serialize_contact(contact)
            institution_id = serialized.get("institution_id")
            serialized["institution_name"] = (
                institutions_map.get(str(institution_id)) if institution_id else None
            )
            serialized_contacts.append(serialized)

        return Response(
            {
                "data": serialized_contacts,
                "institutions": get_institutions_catalog(mongo),
                "treatment_titles": get_treatment_titles_catalog(mongo),
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        mongo = self.get_mongo()
        contact_data = build_contact_payload(request.data)
        errors = validate_contact_payload(contact_data)

        if errors:
            return Response(
                {"error": "Datos invalidos", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contact_data = AuditManager().add_timestampsInfo(
            contact_data, ObjectId(request.user.id)
        )
        contact_payload = ContactsSchema(**contact_data).model_dump(
            exclude_none=False
        )

        result = mongo.connect("contacts").insert_one(contact_payload)
        created = mongo.connect("contacts").find_one({"_id": result.inserted_id})

        return Response(
            {
                "message": "Contacto creado exitosamente",
                "contact": serialize_contact(created),
            },
            status=status.HTTP_201_CREATED,
        )


class ContactDetailView(BaseMovementAPIView):
    def get_contact(self, mongo, contact_id):
        parsed_id = parse_object_id(contact_id)
        if not parsed_id:
            return None

        return mongo.connect("contacts").find_one(
            {"_id": parsed_id, "deleted_at": None}
        )

    def get(self, request, id):
        mongo = self.get_mongo()
        contact = self.get_contact(mongo, id)

        if not contact:
            return Response(
                {"error": "Contacto no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "contact": serialize_contact(contact),
                "institutions": get_institutions_catalog(mongo),
                "treatment_titles": get_treatment_titles_catalog(mongo),
            },
            status=status.HTTP_200_OK,
        )

    def put(self, request, id):
        mongo = self.get_mongo()
        contact = self.get_contact(mongo, id)

        if not contact:
            return Response(
                {"error": "Contacto no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        contact_data = build_contact_payload(request.data)
        errors = validate_contact_payload(contact_data)

        if errors:
            return Response(
                {"error": "Datos invalidos", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contact_data["created_at"] = contact.get("created_at")
        contact_data["created_by"] = contact.get("created_by")
        contact_data["updated_at"] = contact.get("updated_at")
        contact_data["updated_by"] = contact.get("updated_by")
        contact_data["deleted_at"] = contact.get("deleted_at")
        contact_data["deleted_by"] = contact.get("deleted_by")
        contact_data = AuditManager().add_updateInfo(
            contact_data, ObjectId(request.user.id)
        )
        contact_payload = ContactsSchema(**contact_data).model_dump(
            exclude_none=False
        )

        mongo.connect("contacts").update_one(
            {"_id": contact["_id"]},
            {"$set": contact_payload},
        )
        updated = mongo.connect("contacts").find_one({"_id": contact["_id"]})

        return Response(
            {
                "message": "Contacto actualizado exitosamente",
                "contact": serialize_contact(updated),
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, id):
        mongo = self.get_mongo()
        contact = self.get_contact(mongo, id)

        if not contact:
            return Response(
                {"error": "Contacto no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        mongo.connect("contacts").update_one(
            {"_id": contact["_id"]},
            {
                "$set": {
                    "deleted_at": datetime.now(AuditManager.tz),
                    "deleted_by": ObjectId(request.user.id),
                }
            },
        )

        return Response(
            {"message": "Contacto eliminado exitosamente"},
            status=status.HTTP_200_OK,
        )
