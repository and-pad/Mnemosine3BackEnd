import os
from django.conf import settings

from bson import ObjectId
from bson.errors import InvalidId

from user_queries.mongo_queries import PIECES_ALL
from user_queries.views.movements.base import (
    escape_search,
    generation_status_manager,
    parse_bool,
    parse_date,
    parse_object_id,
    parse_object_id_list,
    serialize_mongo,
)

from .constants import REPORT_COLUMNS


def serialize_option(document, label_field="name"):
    if not document:
        return None

    serialized = serialize_mongo(document)
    serialized["id"] = serialized.get("_id")
    serialized["label"] = (
        serialized.get(label_field)
        or serialized.get("name")
        or serialized.get("description")
        or serialized.get("title")
        or ""
    )
    return serialized


def get_report_columns_catalog():
    return [
        {"id": column_id, "label": label}
        for column_id, label in sorted(REPORT_COLUMNS.items(), key=lambda item: item[1])
    ]


def split_csv(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def build_columns_csv(payload):
    selected_columns = split_csv(payload.get("columns"))
    ordered_columns = split_csv(
        payload.get("ordered_columns") or payload.get("columnas_ordenadas")
    )
    custom_order = parse_bool(payload.get("custom_order"))

    if custom_order and ordered_columns:
        allowed_ids = set(selected_columns or ordered_columns)
        final_columns = [column for column in ordered_columns if column in allowed_ids]
    else:
        final_columns = selected_columns

    return ",".join(final_columns), final_columns


def validate_report_payload(payload):
    errors = {}
    _, selected_columns = build_columns_csv(payload)

    if not (payload.get("name") or "").strip():
        errors["name"] = "El nombre es un campo requerido"
    if not selected_columns:
        errors["columns"] = "Debes seleccionar al menos una columna"

    select_type = payload.get("select_type") or "custom"
    if select_type not in {"custom", "all", "all_except"}:
        errors["select_type"] = "El tipo de seleccion no es valido"

    if parse_bool(payload.get("lending_list")):
        if not (payload.get("institution") or "").strip():
            errors["institution"] = "La institucion es requerida para lista de prestamo"
        if not (payload.get("exhibition") or "").strip():
            errors["exhibition"] = "La exposicion es requerida para lista de prestamo"

    return errors


def build_report_payload(payload):
    columns_csv, _ = build_columns_csv(payload)

    return {
        "name": (payload.get("name") or "").strip() or None,
        "description": (payload.get("description") or "").strip() or None,
        "columns": columns_csv or None,
        "pieces_ids": parse_object_id_list(payload.get("pieces_ids", [])),
        "select_type": payload.get("select_type") or "custom",
        "institution": (payload.get("institution") or "").strip() or None,
        "exhibition": (payload.get("exhibition") or "").strip() or None,
        "exhibition_date_start": parse_date(
            payload.get("exhibition_date_start") or payload.get("exhibition_date_ini")
        ),
        "exhibition_date_end": parse_date(
            payload.get("exhibition_date_end") or payload.get("exhibition_date_fin")
        ),
        "lending_list": parse_bool(payload.get("lending_list")),
        "custom_order": parse_bool(payload.get("custom_order")),
    }


def serialize_report(
    document,   
    users_map=None,
):
    serialized = serialize_mongo(document)
    serialized["id"] = serialized.get("_id")
    serialized["columns_list"] = split_csv(serialized.get("columns"))
    serialized["pieces_ids"] = [
        str(piece_id) for piece_id in document.get("pieces_ids") or []
    ]
    serialized["pieces_count"] = len(document.get("pieces_ids") or [])
   
    created_by_id = serialized.get("created_by")
    updated_by_id = serialized.get("updated_by")
    serialized["creator_name"] = (
        (users_map or {}).get(created_by_id) if created_by_id else None
    )
    serialized["updater_name"] = (
        (users_map or {}).get(updated_by_id)
        if updated_by_id
        else serialized.get("creator_name")
    )
    return serialized


def serialize_template(document):
    serialized = serialize_mongo(document)
    serialized["id"] = serialized.get("_id")
    serialized["columns_list"] = split_csv(serialized.get("clm_ord"))
    return serialized


def get_reports_catalogs(mongo):
    institutions = list(
        mongo.connect("institutions")
        .find({"deleted_at": None}, {"name": 1})
        .sort("name", 1)
    )
    exhibitions = list(
        mongo.connect("exhibitions")
        .find({"deleted_at": None}, {"name": 1, "institution_id": 1})
        .sort("name", 1)
    )
    templates = list(
        mongo.connect("template_reports")
        .find({"deleted_at": None}, {"name": 1, "is_custom": 1, "clm_ord": 1})
        .sort("name", 1)
    )

    return {
        "columns_catalog": get_report_columns_catalog(),
        "institutions": [serialize_option(item) for item in institutions],
        "exhibitions": [serialize_option(item) for item in exhibitions],
        "templates": [serialize_template(item) for item in templates],
    }


def get_reports_lookup_maps(mongo):
    institutions = list(
        mongo.connect("institutions").find({"deleted_at": None}, {"name": 1})
    )
    exhibitions = list(
        mongo.connect("exhibitions").find({"deleted_at": None}, {"name": 1})
    )

    return (
        {str(item["_id"]): item.get("name") or "" for item in institutions},
        {str(item["_id"]): item.get("name") or "" for item in exhibitions},
    )


def get_reports_users_map(mongo):
    users = list(
        mongo.connect("authentication_my_user").find(
            {"deleted_at": None},
            {"username": 1, "first_name": 1, "last_name": 1},
        )
    )

    users_map = {}
    for user in users:
        full_name = " ".join(
            part.strip()
            for part in [user.get("first_name") or "", user.get("last_name") or ""]
            if part and part.strip()
        )
        users_map[str(user["_id"])] = full_name or user.get("username") or ""

    return users_map


def get_report_document(mongo, report_id):
    parsed_id = parse_object_id(report_id)
    if not parsed_id:
        return None
    return mongo.connect("reports").find_one({"_id": parsed_id, "deleted_at": None})


def get_template_document(mongo, template_id):
    parsed_id = parse_object_id(template_id)
    if not parsed_id:
        return None
    return mongo.connect("template_reports").find_one(
        {"_id": parsed_id, "deleted_at": None}
    )


def ensure_piece_search_collections(mongo):
    if not mongo.checkIfExistCollection("pieces_search"):
        cursor = mongo.connect("pieces").aggregate(PIECES_ALL)
        documents = list(cursor)
        if documents:
            mongo.connect("pieces_search").insert_many(documents)

    if not mongo.checkIfExistCollection("pieces_search_serialized"):
        generation_status_manager(mongo)


def build_piece_query(search):
    query = {"_id": {"$ne": "1code"}, "deleted_at": None}
    if search:
        regex = escape_search(search)
        query["$or"] = [
            {"inventory_number": regex},
            {"catalog_number": regex},
            {"origin_number": regex},
            {"description_inventory": regex},
            {"description_origin": regex},
            {"research_info.title": regex},
            {"location_info.name": regex},
        ]
    return query


def serialize_piece_row(document):
    serialized = serialize_mongo(document)
    serialized["id"] = serialized.get("_id")
    serialized["title"] = (
        ((serialized.get("research_info") or {}).get("title"))
        or serialized.get("description_inventory")
        or serialized.get("description_origin")
        or "Sin titulo"
    )
    serialized["location_name"] = (
        (serialized.get("location_info") or {}).get("name") or "en prestamo"
    )
    return {
        "id": serialized.get("id"),
        "_id": serialized.get("_id"),
        "inventory_number": serialized.get("inventory_number"),
        "catalog_number": serialized.get("catalog_number"),
        "origin_number": serialized.get("origin_number"),
        "title": serialized.get("title"),
        "location_name": serialized.get("location_name"),
    }


def build_report_pieces_query(report):
    raw_piece_ids = report.get("pieces_ids") or []
    if isinstance(raw_piece_ids, str):
        raw_piece_ids = split_csv(raw_piece_ids)

    selected_ids = []
    for piece_id in raw_piece_ids:
        if piece_id in (None, ""):
            continue
        if isinstance(piece_id, ObjectId):
            selected_ids.append(str(piece_id))
            continue
        try:
            selected_ids.append(str(ObjectId(str(piece_id))))
        except InvalidId:
            selected_ids.append(str(piece_id))

    query = {"_id": {"$ne": "1code"}, "deleted_at": None}
    select_type = report.get("select_type") or "custom"

    if select_type == "all":
        return query

    if select_type == "all_except":
        if selected_ids:
            query["_id"] = {"$nin": ["1code", *selected_ids]}
        return query

    if selected_ids:
        query["_id"] = {"$in": selected_ids}
    else:
        query["_id"] = {"$in": []}
    return query


def get_report_pieces(mongo, report, projection=None):
    ensure_piece_search_collections(mongo)
    query = build_report_pieces_query(report)
    cursor = mongo.connect("pieces_search_serialized").find(query, projection).sort(
        "inventory_number", 1
    )
    return list(cursor)


def filter_report_pieces_by_ids(pieces, selected_piece_ids):
    if not selected_piece_ids:
        return pieces

    allowed = {str(piece_id) for piece_id in selected_piece_ids if piece_id}
    return [piece for piece in pieces if str(piece.get("_id")) in allowed]

def to_object_ids(ids):
    return [ObjectId(i) for i in ids if i]

def get_report_images(mongo, report, thumbnails_path, selected_piece_ids=None):
    if not selected_piece_ids:
        return {}
    if not thumbnails_path:
        thumbnails_path = settings.THUMBNAILS_INVENTORY_PATH

    collection = mongo.connect("photographs")
    selected_piece_ids = to_object_ids(selected_piece_ids)
    cursor = collection.find(
        {"piece_id": {"$in": selected_piece_ids}},
        {"file_name": 1, "piece_id": 1, "main": 1}
    ).sort([
        ("piece_id", 1),   # agrupa visualmente
        ("main", 1)        # prioridad a la principal
    ])

    images_map = {}
    for doc in cursor:
        piece_id = str(doc["piece_id"])

        # 🔒 ya tenemos imagen para esta pieza → skip
        if piece_id in images_map:
            continue

        file_name = doc.get("file_name")
        if not file_name:
            continue

        full_path = os.path.join(thumbnails_path, file_name)

        # opcional pero recomendado (evita PDFs rotos)
        if not os.path.exists(full_path):
            continue

        images_map[piece_id] = full_path

    return images_map
   
