import logging

from bson import ObjectId
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response

from user_queries.shemas.reports_shema import ReportsSchema
from user_queries.views.movements.base import BaseMovementAPIView
from user_queries.views.tools import AuditManager
from django.conf import settings

from .constants import REPORT_COLUMNS
from .helpers import (
    build_piece_query,
    build_report_payload,
    ensure_piece_search_collections,
    filter_report_pieces_by_ids,
    get_report_document,
    get_reports_catalogs,
    get_reports_lookup_maps,
    get_reports_users_map,
    get_report_pieces,
    split_csv,
    serialize_piece_row,
    serialize_report,
    validate_report_payload,
    get_report_images,
)
from .rendering import build_piece_section, render_report_pdf

logger = logging.getLogger(__name__)


class ReportsView(BaseMovementAPIView):
    def get(self, request):
        mongo = self.get_mongo()
        reports = list(mongo.connect("reports").find({"deleted_at": None}).sort("name", 1))
        institutions_map, exhibitions_map = get_reports_lookup_maps(mongo)
        users_map = get_reports_users_map(mongo)

        return Response(
            {
                "data": [
                    serialize_report(item, institutions_map, exhibitions_map, users_map)
                    for item in reports
                ]
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        mongo = self.get_mongo()
        errors = validate_report_payload(request.data)

        if errors:
            return Response(
                {"error": "Datos invalidos", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        report_data = build_report_payload(request.data)
        report_data = AuditManager().add_timestampsInfo(
            report_data, ObjectId(request.user.id)
        )
        report_payload = ReportsSchema(**report_data).model_dump(exclude_none=False)
        result = mongo.connect("reports").insert_one(report_payload)
        created = mongo.connect("reports").find_one({"_id": result.inserted_id})
        institutions_map, exhibitions_map = get_reports_lookup_maps(mongo)
        users_map = get_reports_users_map(mongo)

        return Response(
            {
                "message": "Reporte creado exitosamente",
                "report": serialize_report(
                    created, institutions_map, exhibitions_map, users_map
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class ReportsMetaView(BaseMovementAPIView):
    def get(self, request):
        mongo = self.get_mongo()
        return Response(get_reports_catalogs(mongo), status=status.HTTP_200_OK)


class ReportDetailView(BaseMovementAPIView):
    def get(self, request, id):
        mongo = self.get_mongo()
        report = get_report_document(mongo, id)

        if not report:
            return Response(
                {"error": "Reporte no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        institutions_map, exhibitions_map = get_reports_lookup_maps(mongo)
        users_map = get_reports_users_map(mongo)
        response_data = get_reports_catalogs(mongo)
        response_data["report"] = serialize_report(
            report, institutions_map, exhibitions_map, users_map
        )
        return Response(response_data, status=status.HTTP_200_OK)

    def put(self, request, id):
        mongo = self.get_mongo()
        report = get_report_document(mongo, id)

        if not report:
            return Response(
                {"error": "Reporte no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        errors = validate_report_payload(request.data)
        if errors:
            return Response(
                {"error": "Datos invalidos", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        report_data = build_report_payload(request.data)
        report_data["created_at"] = report.get("created_at")
        report_data["created_by"] = report.get("created_by")
        report_data["deleted_at"] = report.get("deleted_at")
        report_data["deleted_by"] = report.get("deleted_by")
        report_data = AuditManager().add_updateInfo(
            report_data, ObjectId(request.user.id)
        )
        report_payload = ReportsSchema(**report_data).model_dump(exclude_none=False)

        mongo.connect("reports").update_one(
            {"_id": report["_id"]},
            {"$set": report_payload},
        )
        updated = mongo.connect("reports").find_one({"_id": report["_id"]})
        institutions_map, exhibitions_map = get_reports_lookup_maps(mongo)
        users_map = get_reports_users_map(mongo)

        return Response(
            {
                "message": "Reporte actualizado exitosamente",
                "report": serialize_report(
                    updated, institutions_map, exhibitions_map, users_map
                ),
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, id):
        mongo = self.get_mongo()
        report = get_report_document(mongo, id)

        if not report:
            return Response(
                {"error": "Reporte no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        delete_payload = AuditManager().add_updateInfo({}, ObjectId(request.user.id))
        delete_payload["deleted_at"] = delete_payload.get("updated_at")
        delete_payload["deleted_by"] = delete_payload.get("updated_by")

        mongo.connect("reports").update_one(
            {"_id": report["_id"]},
            {"$set": delete_payload},
        )

        return Response(
            {"message": "Reporte eliminado exitosamente"},
            status=status.HTTP_200_OK,
        )


class ReportPiecesView(BaseMovementAPIView):
    def get(self, request):
        mongo = self.get_mongo()
        ensure_piece_search_collections(mongo)

        search = (request.query_params.get("search") or "").strip()
        page = max(int(request.query_params.get("page") or 1), 1)
        page_size = max(min(int(request.query_params.get("page_size") or 10), 50), 1)
        query = build_piece_query(search)

        total = mongo.connect("pieces_search_serialized").count_documents(query)
        documents = list(
            mongo.connect("pieces_search_serialized")
            .find(
                query,
                {
                    "inventory_number": 1,
                    "catalog_number": 1,
                    "origin_number": 1,
                    "description_inventory": 1,
                    "description_origin": 1,
                    "research_info.title": 1,
                    "location_info.name": 1,
                },
            )
            .sort("inventory_number", 1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )

        return Response(
            {
                "data": [serialize_piece_row(item) for item in documents],
                "page": page,
                "page_size": page_size,
                "total": total,
            },
            status=status.HTTP_200_OK,
        )


class ReportPreviewView(BaseMovementAPIView):
    def get(self, request, id):
        mongo = self.get_mongo()
        report = get_report_document(mongo, id)

        if not report:
            return Response(
                {"error": "Reporte no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        institutions_map, exhibitions_map = get_reports_lookup_maps(mongo)
        users_map = get_reports_users_map(mongo)
        serialized_report = serialize_report(
            report, institutions_map, exhibitions_map, users_map
        )
        selected_columns = serialized_report.get("columns_list") or []
        pieces = get_report_pieces(mongo, report)
        rendered_pieces = [
            build_piece_section(piece, selected_columns)
            for piece in pieces
        ]

        return Response(
            {
                "report": serialized_report,
                "columns": [
                    {"id": column_id, "label": REPORT_COLUMNS.get(column_id, column_id)}
                    for column_id in selected_columns
                ],
                "pieces": rendered_pieces,
            },
            status=status.HTTP_200_OK,
        )


class ReportPdfView(BaseMovementAPIView):
    def get(self, request, id):
        mongo = self.get_mongo()
        report = get_report_document(mongo, id)

        if not report:
            return Response(
                {"error": "Reporte no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        #institutions_map, exhibitions_map = get_reports_lookup_maps(mongo)
        


        users_map = get_reports_users_map(mongo)
        serialized_report = serialize_report(
            report, users_map
        )

        selected_columns = serialized_report.get("columns_list") or []
        pieces = get_report_pieces(mongo, report)
        selected_piece_ids = split_csv(request.query_params.get("selected_piece_ids"))
        pieces = filter_report_pieces_by_ids(pieces, selected_piece_ids)

        rendered_pieces = [
            build_piece_section(piece, selected_columns)
            for piece in pieces
        ]

        TumbnailsInventoryPath = settings.THUMBNAILS_INVENTORY_PATH
        images = get_report_images(mongo, report, TumbnailsInventoryPath)


        try:
            _, pdf_bytes = render_report_pdf(serialized_report, rendered_pieces)
        except Exception as exc:
            logger.exception("No fue posible generar el PDF del reporte %s", id)
            return Response(
                {
                    "error": "No fue posible generar el PDF del reporte",
                    "details": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="reporte_{id}.pdf"'
        return response
