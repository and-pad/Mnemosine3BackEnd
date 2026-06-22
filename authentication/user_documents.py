import logging

from bson import ObjectId


logger = logging.getLogger(__name__)

LEGACY_USER_COUNTER_ID = "user_id_counter"
USER_COUNTER_COLLECTION = "app_counters"
USER_COUNTER_KEY = "authentication_my_user:id"


def build_user_collection_query(extra_filter=None):
    filters = [
        {
            "$or": [
                {"username": {"$exists": True}},
                {"email": {"$exists": True}},
                {"password": {"$exists": True}},
                {"name": {"$exists": True}},
                {"NewName": {"$exists": True}},
                {"NewEmail": {"$exists": True}},
            ]
        }
    ]
    if extra_filter:
        filters.append(extra_filter)
    if len(filters) == 1:
        return filters[0]
    return {"$and": filters}


def get_user_username(user):
    for field in ("username", "name", "NewName", "email", "NewEmail"):
        value = user.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    numeric_id = user.get("id")
    if numeric_id is not None:
        return f"Usuario {numeric_id}"
    return "Usuario sin nombre"


def get_user_email(user):
    for field in ("email", "NewEmail", "mail"):
        value = user.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def get_user_lookup_ids(user):
    lookup_ids = []
    object_id = user.get("_id")
    if object_id is not None:
        lookup_ids.append(object_id)

    numeric_id = user.get("id")
    if isinstance(numeric_id, int):
        lookup_ids.append(numeric_id)

    return lookup_ids


def log_user_document_warning(user, *, context):
    missing_fields = []
    if not user.get("username"):
        missing_fields.append("username")
    if not user.get("email"):
        missing_fields.append("email")
    if not user.get("password"):
        missing_fields.append("password")

    if not missing_fields:
        return

    logger.warning(
        "Incomplete user document detected in %s: _id=%s missing=%s keys=%s",
        context,
        user.get("_id"),
        ",".join(missing_fields),
        sorted(user.keys()),
    )


def normalize_user_document(user, *, context):
    log_user_document_warning(user, context=context)
    return {
        "id": str(user.get("_id")) if user.get("_id") is not None else None,
        "object_id": user.get("_id"),
        "numeric_id": user.get("id") if isinstance(user.get("id"), int) else None,
        "username": get_user_username(user),
        "email": get_user_email(user),
        "is_active": user.get("is_active", True),
        "raw": user,
    }


def is_valid_user_object_id(value):
    return isinstance(value, ObjectId)
