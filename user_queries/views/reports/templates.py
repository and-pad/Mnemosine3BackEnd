from bson import ObjectId
from rest_framework import status
from rest_framework.response import Response

from user_queries.shemas.template_reports_shema import TemplateReportsSchema
from user_queries.views.movements.base import BaseMovementAPIView, parse_bool
from user_queries.views.tools import AuditManager

from .helpers import get_template_document, serialize_template, split_csv


def validate_template_payload(payload):
    errors = {}
    if not (payload.get("name") or "").strip():
        errors["name"] = "El nombre es un campo requerido"
    columns = split_csv(payload.get("clm_ord") or payload.get("columns"))
    if not columns:
        errors["clm_ord"] = "Debes seleccionar al menos una columna"
    return errors


def build_template_payload(payload):
    columns = split_csv(payload.get("clm_ord") or payload.get("columns"))
    return {
        "name": (payload.get("name") or "").strip() or None,
        "is_custom": parse_bool(payload.get("is_custom")),
        "clm_ord": ",".join(columns) or None,
    }


class ReportTemplatesView(BaseMovementAPIView):
    def get(self, request):
        mongo = self.get_mongo()
        templates = list(
            mongo.connect("template_reports")
            .find({"deleted_at": None})
            .sort("name", 1)
        )
        return Response(
            {"data": [serialize_template(item) for item in templates]},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        mongo = self.get_mongo()
        errors = validate_template_payload(request.data)

        if errors:
            return Response(
                {"error": "Datos invalidos", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        template_data = build_template_payload(request.data)
        template_data = AuditManager().add_timestampsInfo(
            template_data, ObjectId(request.user.id)
        )
        template_payload = TemplateReportsSchema(**template_data).model_dump(
            exclude_none=False
        )
        result = mongo.connect("template_reports").insert_one(template_payload)
        created = mongo.connect("template_reports").find_one({"_id": result.inserted_id})

        return Response(
            {
                "message": "Plantilla guardada exitosamente",
                "template": serialize_template(created),
            },
            status=status.HTTP_201_CREATED,
        )


class ReportTemplateDetailView(BaseMovementAPIView):
    def delete(self, request, id):
        mongo = self.get_mongo()
        template = get_template_document(mongo, id)

        if not template:
            return Response(
                {"error": "Plantilla no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        delete_payload = AuditManager().add_updateInfo({}, ObjectId(request.user.id))
        delete_payload["deleted_at"] = delete_payload.get("updated_at")
        delete_payload["deleted_by"] = delete_payload.get("updated_by")

        mongo.connect("template_reports").update_one(
            {"_id": template["_id"]},
            {"$set": delete_payload},
        )

        return Response(
            {"message": "Plantilla eliminada exitosamente"},
            status=status.HTTP_200_OK,
        )
