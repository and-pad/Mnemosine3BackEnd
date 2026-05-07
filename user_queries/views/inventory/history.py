import json
from datetime import datetime

from bson import ObjectId
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.custom_jwt import CustomJWTAuthentication
from user_queries.driver_database.mongo import Mongo


def serialize_mongo(document):
    return json.loads(json.dumps(document, default=str))


def parse_object_id(value):
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


def to_iso_datetime(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def get_user_map(mongo, object_ids):
    valid_ids = [object_id for object_id in object_ids if isinstance(object_id, ObjectId)]
    if not valid_ids:
        return {}

    users = list(
        mongo.connect("authentication_my_user").find(
            {"_id": {"$in": valid_ids}},
            {"username": 1, "email": 1},
        )
    )
    return {
        user["_id"]: {
            "_id": str(user["_id"]),
            "username": user.get("username") or "Usuario desconocido",
            "email": user.get("email") or "",
        }
        for user in users
    }


def get_user_info(user_map, raw_user_id):
    parsed_user_id = parse_object_id(raw_user_id)
    if not parsed_user_id:
        return None
    return user_map.get(parsed_user_id)


def normalize_simple_value(value):
    if isinstance(value, dict):
        if "file_name" in value:
            return value.get("file_name")
        if "title" in value and len(value) == 1:
            return value.get("title")
        if "name" in value and len(value) == 1:
            return value.get("name")
        if "title" in value:
            return value.get("title")
        if "name" in value:
            return value.get("name")
        if "_id" in value and len(value) == 1:
            return value.get("_id")
        return ", ".join(
            f"{key}: {normalize_simple_value(item)}" for key, item in value.items()
        )
    if isinstance(value, list):
        return ", ".join(str(normalize_simple_value(item)) for item in value)
    return value


def normalize_special_change(field_name, payload):
    if field_name == "new_pics":
        file_names = [item.get("file_name") or "Fotografia nueva" for item in payload or []]
        return {
            "field": field_name,
            "label": humanize_field_name(field_name),
            "old_value": None,
            "new_value": ", ".join(file_names) if file_names else "Se agregaron fotografias",
        }

    if field_name == "new_docs":
        names = [
            item.get("name") or item.get("title") or item.get("file_name") or "Documento nuevo"
            for item in payload or []
        ]
        return {
            "field": field_name,
            "label": humanize_field_name(field_name),
            "old_value": None,
            "new_value": ", ".join(names) if names else "Se agregaron documentos",
        }

    if field_name in {"changed_pics", "changed_docs"}:
        names = [
            item.get("file_name") or item.get("name") or item.get("title") or "Archivo reemplazado"
            for item in payload or []
        ]
        return {
            "field": field_name,
            "label": humanize_field_name(field_name),
            "old_value": "Archivo anterior",
            "new_value": ", ".join(names) if names else "Archivo reemplazado",
        }

    if field_name in {"changed_pics_info", "changed_docs_info"}:
        names = []
        for _, item in (payload or {}).items():
            names.append(item.get("title") or item.get("description") or item.get("name") or "Metadatos actualizados")
        return {
            "field": field_name,
            "label": humanize_field_name(field_name),
            "old_value": "Metadatos anteriores",
            "new_value": ", ".join(names) if names else "Metadatos actualizados",
        }

    return None


def humanize_field_name(field_name):
    mapping = {
        "gender_id": "Genero",
        "subgender_id": "Subgenero",
        "type_object_id": "Tipo de objeto",
        "dominant_material_id": "Material dominante",
        "inventory_number": "Numero de inventario",
        "catalog_number": "Numero de catalogo",
        "origin_number": "Numero de origen",
        "description_origin": "Descripcion origen",
        "description_inventory": "Descripcion inventario",
        "changed_pics_info": "Informacion de fotografias",
        "changed_docs_info": "Informacion de documentos",
        "changed_pics": "Fotografias reemplazadas",
        "changed_docs": "Documentos reemplazados",
        "new_pics": "Fotografias nuevas",
        "new_docs": "Documentos nuevos",
        "new_piece": "Alta inicial",
    }
    return mapping.get(field_name, field_name.replace("_", " ").capitalize())


def normalize_change_item(field_name, payload):
    special_change = normalize_special_change(field_name, payload)
    if special_change:
        return special_change

    if isinstance(payload, dict) and "oldValue" in payload and "newValue" in payload:
        return {
            "field": field_name,
            "label": humanize_field_name(field_name),
            "old_value": normalize_simple_value(payload.get("oldValue")),
            "new_value": normalize_simple_value(payload.get("newValue")),
        }

    return {
        "field": field_name,
        "label": humanize_field_name(field_name),
        "old_value": None,
        "new_value": normalize_simple_value(payload),
    }


def get_entry_status(entry):
    approved_value = entry.get("approved_rejected")
    if approved_value is True:
        return "Autorizado"
    if approved_value == "rejected" or approved_value is False:
        return "Rechazado"
    return "Pendiente"


def get_entry_action_type(entry):
    if entry.get("new_piece"):
        return "Creacion"
    return "Edicion"


def normalize_history_entry(entry, user_map):
    excluded_fields = {
        "_id",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "piece_id",
        "approved_rejected_by",
        "approved_rejected",
        "changed_by_module_id",
        "deleted_at",
        "deleted_by",
    }

    created_by = get_user_info(user_map, entry.get("created_by"))
    approved_by = get_user_info(user_map, entry.get("approved_rejected_by"))
    serialized_entry = serialize_mongo(entry)

    changes = []
    if entry.get("new_piece"):
        for field_name, value in (entry.get("new_piece") or {}).items():
            changes.append(
                {
                    "field": field_name,
                    "label": humanize_field_name(field_name),
                    "old_value": None,
                    "new_value": normalize_simple_value(value),
                }
            )
    else:
        for field_name, value in entry.items():
            if field_name in excluded_fields:
                continue
            changes.append(normalize_change_item(field_name, value))

    return {
        "id": serialized_entry.get("_id"),
        "piece_id": serialized_entry.get("piece_id"),
        "action_type": get_entry_action_type(entry),
        "status": get_entry_status(entry),
        "created_at": to_iso_datetime(entry.get("created_at")),
        "updated_at": to_iso_datetime(entry.get("updated_at")),
        "created_by": created_by,
        "approved_rejected_by": approved_by,
        "changes": changes,
        "raw_reference": {
            "new_piece": serialized_entry.get("new_piece"),
            "new_pics": serialized_entry.get("new_pics"),
            "new_docs": serialized_entry.get("new_docs"),
            "changed_pics": serialized_entry.get("changed_pics"),
            "changed_docs": serialized_entry.get("changed_docs"),
            "changed_pics_info": serialized_entry.get("changed_pics_info"),
            "changed_docs_info": serialized_entry.get("changed_docs_info"),
        },
    }


class InventoryHistoryView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def get(self, request, _id):
        parsed_piece_id = parse_object_id(_id)
        if not parsed_piece_id:
            return Response(
                {"error": "Pieza invalida"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mongo = Mongo()
        piece = mongo.connect("pieces").find_one(
            {"_id": parsed_piece_id},
            {"_id": 1, "inventory_number": 1, "catalog_number": 1},
        )
        if not piece:
            return Response(
                {"error": "Pieza no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        history_entries = list(
            mongo.connect("inventory_change_approvals")
            .find({"piece_id": parsed_piece_id})
            .sort("created_at", -1)
        )

        # Fallback para posibles altas antiguas aprobadas sin piece_id enlazado.
        if not history_entries:
            maybe_creation_entries = list(
                mongo.connect("inventory_change_approvals").find(
                    {
                        "new_piece.inventory_number": piece.get("inventory_number"),
                        "approved_rejected": True,
                    }
                )
            )
            if maybe_creation_entries:
                history_entries = maybe_creation_entries

        user_ids = []
        for entry in history_entries:
            if entry.get("created_by"):
                user_ids.append(entry.get("created_by"))
            if entry.get("approved_rejected_by"):
                approved_by = parse_object_id(entry.get("approved_rejected_by"))
                if approved_by:
                    user_ids.append(approved_by)

        user_map = get_user_map(mongo, user_ids)
        normalized_history = [
            normalize_history_entry(entry, user_map) for entry in history_entries
        ]

        return Response(
            {
                "piece_id": str(parsed_piece_id),
                "history": normalized_history,
                "has_history": bool(normalized_history),
            },
            status=status.HTTP_200_OK,
        )
