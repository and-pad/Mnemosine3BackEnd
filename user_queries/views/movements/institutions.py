from datetime import datetime

from bson import ObjectId
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

from user_queries.shemas.institutions_shema import InstitutionsSchema
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
        or serialized.get("description")
        or serialized.get("title")
        or ""
    )
    return serialized


def serialize_institution(document):
    serialized = serialize_mongo(document)
    serialized["id"] = serialized.get("_id")
    return serialized


def get_country_catalog(mongo):
    countries = list(
        mongo.connect("countries")
        .find({"deleted_at": None}, {"name": 1, "iso2": 1, "iso3": 1})
        .sort("name", 1)
    )
    return [serialize_catalog_option(item) for item in countries]


def get_state_catalog(mongo):
    states = list(
        mongo.connect("states")
        .find({"deleted_at": None}, {"name": 1, "description": 1, "country_id": 1})
        .sort([("country_id", 1), ("name", 1)])
    )
    return [serialize_catalog_option(item) for item in states]


def build_institution_payload(payload):
    return {
        "name": payload.get("name"),
        "address": payload.get("address"),
        "city": payload.get("city"),
        "country_id": parse_object_id(payload.get("country_id")),
        "state_id": parse_object_id(payload.get("state_id")),
        "zip_code": payload.get("zip_code"),
        "phone": payload.get("phone"),
        "phone2": payload.get("phone2"),
        "fax": payload.get("fax"),
        "email": payload.get("email"),
        "web_site": payload.get("web_site"),
        "business_activity": payload.get("business_activity"),
        "rfc": payload.get("rfc"),
    }


def validate_institution_payload(payload):
    errors = {}

    if not payload.get("name"):
        errors["name"] = "El nombre es un campo requerido"
    if not payload.get("address"):
        errors["address"] = "La direccion es un campo requerido"
    if not payload.get("phone"):
        errors["phone"] = "El numero de telefono es un campo requerido"
    elif isinstance(payload["phone"], str) and len(payload["phone"].strip()) < 7:
        errors["phone"] = "El numero de telefono debe contener al menos 7 caracteres"
    if not payload.get("country_id"):
        errors["country_id"] = "El pais es un campo requerido"
    if payload.get("state_id") and not payload.get("country_id"):
        errors["state_id"] = "No se puede asignar un estado sin pais"

    return errors


class InstitutionsView(BaseMovementAPIView):
    def get(self, request):
        mongo = self.get_mongo()
        search = (request.query_params.get("search") or "").strip()

        query = {"deleted_at": None}
        if search:
            regex = escape_search(search)
            query["$or"] = [
                {"name": regex},
                {"address": regex},
                {"city": regex},
                {"phone": regex},
                {"email": regex},
                {"business_activity": regex},
                {"rfc": regex},
            ]

        institutions = list(mongo.connect("institutions").find(query).sort("name", 1))

        return Response(
            {
                "data": [serialize_institution(item) for item in institutions],
                "countries": get_country_catalog(mongo),
                "states": get_state_catalog(mongo),
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        mongo = self.get_mongo()
        institution_data = build_institution_payload(request.data)
        errors = validate_institution_payload(institution_data)

        if errors:
            return Response(
                {"error": "Datos invalidos", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        institution_data = AuditManager().add_timestampsInfo(
            institution_data, ObjectId(request.user.id)
        )
        institution_payload = InstitutionsSchema(**institution_data).model_dump(
            exclude_none=False
        )

        result = mongo.connect("institutions").insert_one(institution_payload)
        created = mongo.connect("institutions").find_one({"_id": result.inserted_id})

        return Response(
            {
                "message": "Institucion creada exitosamente",
                "institution": serialize_institution(created),
            },
            status=status.HTTP_201_CREATED,
        )


class InstitutionDetailView(BaseMovementAPIView):
    def get_institution(self, mongo, institution_id):
        parsed_id = parse_object_id(institution_id)
        if not parsed_id:
            return None

        return mongo.connect("institutions").find_one(
            {"_id": parsed_id, "deleted_at": None}
        )

    def get(self, request, id):
        mongo = self.get_mongo()
        institution = self.get_institution(mongo, id)

        if not institution:
            return Response(
                {"error": "Institucion no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "institution": serialize_institution(institution),
                "countries": get_country_catalog(mongo),
                "states": get_state_catalog(mongo),
            },
            status=status.HTTP_200_OK,
        )

    def put(self, request, id):
        mongo = self.get_mongo()
        institution = self.get_institution(mongo, id)

        if not institution:
            return Response(
                {"error": "Institucion no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        institution_data = build_institution_payload(request.data)
        errors = validate_institution_payload(institution_data)

        if errors:
            return Response(
                {"error": "Datos invalidos", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        institution_data["created_at"] = institution.get("created_at")
        institution_data["created_by"] = institution.get("created_by")
        institution_data["updated_at"] = institution.get("updated_at")
        institution_data["updated_by"] = institution.get("updated_by")
        institution_data["deleted_at"] = institution.get("deleted_at")
        institution_data["deleted_by"] = institution.get("deleted_by")
        institution_data = AuditManager().add_updateInfo(
            institution_data, ObjectId(request.user.id)
        )
        institution_payload = InstitutionsSchema(**institution_data).model_dump(
            exclude_none=False
        )

        mongo.connect("institutions").update_one(
            {"_id": institution["_id"]},
            {"$set": institution_payload},
        )
        updated = mongo.connect("institutions").find_one({"_id": institution["_id"]})

        return Response(
            {
                "message": "Institucion actualizada exitosamente",
                "institution": serialize_institution(updated),
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, id):
        mongo = self.get_mongo()
        institution = self.get_institution(mongo, id)

        if not institution:
            return Response(
                {"error": "Institucion no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if institution.get("name") == getattr(settings, "INSTITUTION_NAME", None):
            return Response(
                {"error": "No se puede eliminar la institucion interna configurada"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mongo.connect("institutions").update_one(
            {"_id": institution["_id"]},
            {
                "$set": {
                    "deleted_at": datetime.now(AuditManager.tz),
                    "deleted_by": ObjectId(request.user.id),
                }
            },
        )

        return Response(
            {"message": "Institucion eliminada exitosamente"},
            status=status.HTTP_200_OK,
        )
