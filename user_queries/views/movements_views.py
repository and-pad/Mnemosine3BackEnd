import json
import re
from datetime import datetime

from bson import ObjectId
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.custom_jwt import CustomJWTAuthentication
from user_queries.driver_database.mongo import Mongo
from user_queries.shemas.movements_shema import MovementsSchema
from user_queries.views.tools import AuditManager


def parse_object_id(value):
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


def parse_object_id_list(values):
    if not isinstance(values, list):
        return []
    return [object_id for object_id in (parse_object_id(value) for value in values) if object_id]


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
        "movements_id": int(payload.get("movements_id") or 0) or get_next_movement_id(mongo),
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
        "institution_ids": [str(item) for item in document.get("institution_ids") or []],
        "internal_institution_id": str(
            internal_institution_id
            or (document.get("institution_ids") or [None])[0]
            or ""
        ),
        "contact_ids": [str(item) for item in document.get("contact_ids") or []],
        "guard_contact_ids": [str(item) for item in document.get("guard_contact_ids") or []],
        "exhibition_id": str(document.get("exhibition_id")) if document.get("exhibition_id") else None,
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


class BaseMovementAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def get_mongo(self):
        return Mongo()


class MovementsManage(BaseMovementAPIView):
    def get(self, request):

        mongo = self.get_mongo()

        page = int(request.query_params.get("page", 1))
        per_page = int(request.query_params.get("per_page", 10))
        search = request.query_params.get("search", "")

        skip = (page - 1) * per_page
        query = {"deleted_at": None}

        exhibitions_map = {}
        institutions_map = {}

        if search:
            regex = (
                {"$regex": f"{re.escape(search)}", "$options": "i"}
                if search
                else {"$regex": f"{search}", "$options": "i"}
            )
            exhibitions_cursor = mongo.connect("exhibitions").find(
                {"name": regex, "deleted_at": None}, {"_id": 1, "name": 1}
            )
            exhibitions = list(exhibitions_cursor)
            exhibition_ids = [e["_id"] for e in exhibitions]
            exhibitions_map = {e["_id"]: e["name"] for e in exhibitions}

            institutions_cursor = mongo.connect("institutions").find(
                {"name": regex, "deleted_at": None}, {"_id": 1, "name": 1}
            )
            institutions = list(institutions_cursor)
            institution_ids = [i["_id"] for i in institutions]
            institutions_map = {i["_id"]: i["name"] for i in institutions}

            pieces_cursor = mongo.connect("pieces").find(
                {"catalog_number": regex, "deleted_at": None},
                {"_id": 1, "catalog_number": 1},
            )
            pieces = list(pieces_cursor)
            piece_ids = [p["_id"] for p in pieces]
            pieces_map = {p["_id"]: p["catalog_number"] for p in pieces}

            if (
                not exhibition_ids
                and not institution_ids
                and not piece_ids
                and not search.isdigit()
            ):
                return Response(
                    {
                        "data": [],
                        "page": page,
                        "per_page": per_page,
                        "total": 0,
                    },
                    status=status.HTTP_200_OK,
                )

            or_conditions = [
                {"exhibition_id": {"$in": exhibition_ids}},
                {"institution_ids": {"$in": institution_ids}},
                {"pieces_ids": {"$in": piece_ids}},
            ]

            if search.isdigit():
                or_conditions.append(
                    {
                        "$expr": {
                            "$regexMatch": {
                                "input": {"$toString": "$movements_id"},
                                "regex": search,
                            }
                        }
                    }
                )

            query = {"deleted_at": None, "$or": or_conditions}

        movements_collection = mongo.connect("movements")
        total = movements_collection.count_documents(query)
        cursor = (
            movements_collection.find(query)
            .sort("movements_id", -1)
            .skip(skip)
            .limit(per_page)
        )

        documents = list(cursor)
        doc_exhibition_ids = list(
            set(
                doc.get("exhibition_id")
                for doc in documents
                if doc.get("exhibition_id")
            )
        )

        missing_exhibition_ids = [
            eid for eid in doc_exhibition_ids if eid not in exhibitions_map
        ]

        if missing_exhibition_ids:
            exhibitions_cursor = mongo.connect("exhibitions").find(
                {"_id": {"$in": missing_exhibition_ids}}, {"name": 1}
            )

            for exhibition in exhibitions_cursor:
                exhibitions_map[exhibition["_id"]] = exhibition["name"]

        all_institution_ids = set()
        for doc in documents:
            for institution_id in doc.get("institution_ids", []):
                all_institution_ids.add(institution_id)

        missing_institution_ids = [
            institution_id
            for institution_id in all_institution_ids
            if institution_id not in institutions_map
        ]

        if missing_institution_ids:
            institutions_cursor = mongo.connect("institutions").find(
                {"_id": {"$in": list(missing_institution_ids)}}, {"name": 1}
            )

            for institution in institutions_cursor:
                institutions_map[institution["_id"]] = institution["name"]

        pieces_map = {}
        all_pieces_ids = set()
        for doc in documents:
            for piece_id in doc.get("pieces_ids") or []:
                all_pieces_ids.add(piece_id)

        if all_pieces_ids:
            pieces_cursor = mongo.connect("pieces").find(
                {"_id": {"$in": list(all_pieces_ids)}}, {"catalog_number": 1}
            )
            pieces_map = {piece["_id"]: piece["catalog_number"] for piece in pieces_cursor}

        movements_data = [
            {
                "id": int(mov["movements_id"]),
                "departure_date": mov.get("departure_date"),
                "exhibition_name": exhibitions_map.get(mov.get("exhibition_id")),
                "institution_names": ", ".join(
                    institutions_map[institution_id]
                    for institution_id in mov.get("institution_ids") or []
                    if institution_id in institutions_map
                ),
                "pieces": ", ".join(
                    pieces_map[piece_id]
                    for piece_id in (mov.get("pieces_ids") or [])
                    if piece_id in pieces_map
                ),
                "pieces_count": len(
                    set(str(piece_id) for piece_id in (mov.get("pieces_ids") or []))
                    - set(
                        str(piece_id)
                        for piece_id in (mov.get("pieces_ids_arrived") or [])
                    )
                ),
                "authorized_by_movements": str(mov.get("authorized_by_movements"))
                if mov.get("authorized_by_movements")
                else None,
                "itinerant": mov.get("itinerant"),
            }
            for mov in documents
        ]

        return Response(
            {
                "data": movements_data,
                "page": page,
                "per_page": per_page,
                "total": total,
            },
            status=status.HTTP_200_OK,
        )


class MovementContactsView(BaseMovementAPIView):
    def get(self, request, institution_ids):
        mongo = self.get_mongo()
        parsed_ids = parse_object_id_list(
            [value for value in institution_ids.split(",") if value]
        )
        return Response(
            get_contacts_by_institutions(mongo, parsed_ids),
            status=status.HTTP_200_OK,
        )


class MovementExhibitionsView(BaseMovementAPIView):
    def get(self, request, institution_ids):
        mongo = self.get_mongo()
        parsed_ids = parse_object_id_list(
            [value for value in institution_ids.split(",") if value]
        )
        return Response(
            get_exhibitions_by_institutions(mongo, parsed_ids),
            status=status.HTTP_200_OK,
        )


class MovementVenuesView(BaseMovementAPIView):
    def get(self, request, institution_ids):
        mongo = self.get_mongo()
        parsed_ids = parse_object_id_list(
            [value for value in institution_ids.split(",") if value]
        )
        return Response(
            get_venues_by_institutions(mongo, parsed_ids),
            status=status.HTTP_200_OK,
        )


class MovementsNew(BaseMovementAPIView):
    def get(self, request, id=None):
        mongo = self.get_mongo()
        response_data = get_institutions_payload(mongo)

        if not id:
            response_data["movement"] = None
            response_data["contacts"] = []
            response_data["exhibitions"] = []
            response_data["venues"] = []
            return Response(response_data, status=status.HTTP_200_OK)

        movement = mongo.connect("movements").find_one(
            {"movements_id": int(id), "deleted_at": None}
        )

        if not movement:
            return Response(
                {"error": "Movimiento no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        internal_institution = response_data.get("internal_institution")
        internal_institution_id = (
            internal_institution.get("_id") if internal_institution else None
        )
        selected_institution_ids = get_selected_institution_ids(
            {
                "movement_type": movement.get("movement_type"),
                "institution_ids": [str(item) for item in movement.get("institution_ids") or []],
                "internal_institution_id": str(internal_institution_id)
                if internal_institution_id
                else None,
            }
        )

        response_data["movement"] = serialize_form_movement(
            movement, internal_institution_id
        )
        response_data["contacts"] = get_contacts_by_institutions(
            mongo, selected_institution_ids
        )
        response_data["exhibitions"] = get_exhibitions_by_institutions(
            mongo, selected_institution_ids
        )
        response_data["venues"] = get_venues_by_institutions(
            mongo, selected_institution_ids
        )
        return Response(response_data, status=status.HTTP_200_OK)

    def post(self, request, id=None):
        mongo = self.get_mongo()
        movement_data = normalize_movement_payload(request.data, mongo)
        movement_data = AuditManager().add_timestampsInfo(
            movement_data, ObjectId(request.user.id)
        )
        movement = MovementsSchema(**movement_data).model_dump(exclude_none=False)
        result = mongo.connect("movements").insert_one(movement)

        return Response(
            {
                "id": movement_data["movements_id"],
                "_id": str(result.inserted_id),
                "movement_id": movement_data["movements_id"],
                "message": "Movimiento creado exitosamente",
            },
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, id):
        mongo = self.get_mongo()
        existing_movement = mongo.connect("movements").find_one(
            {"movements_id": int(id), "deleted_at": None}
        )

        if not existing_movement:
            return Response(
                {"error": "Movimiento no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        movement_data = normalize_movement_payload(
            {**request.data, "movements_id": existing_movement["movements_id"]},
            mongo,
        )
        movement_data["pieces_ids"] = existing_movement.get("pieces_ids") or []
        movement_data["pieces_ids_arrived"] = existing_movement.get("pieces_ids_arrived") or []
        movement_data["arrival_information"] = existing_movement.get("arrival_information") or []
        movement_data["arrival_date"] = existing_movement.get("arrival_date")
        movement_data["arrival_location_id"] = existing_movement.get("arrival_location_id")
        movement_data["type_arrival"] = existing_movement.get("type_arrival")
        movement_data["authorized_by_movements"] = existing_movement.get(
            "authorized_by_movements"
        )
        movement_data["created_at"] = existing_movement.get("created_at")
        movement_data["created_by"] = existing_movement.get("created_by")
        movement_data["deleted_at"] = existing_movement.get("deleted_at")
        movement_data["deleted_by"] = existing_movement.get("deleted_by")
        movement_data = AuditManager().add_updateInfo(
            movement_data, ObjectId(request.user.id)
        )
        movement = MovementsSchema(**movement_data).model_dump(exclude_none=False)

        mongo.connect("movements").update_one(
            {"_id": existing_movement["_id"]},
            {"$set": movement},
        )

        return Response(
            {
                "id": existing_movement["movements_id"],
                "_id": str(existing_movement["_id"]),
                "movement_id": existing_movement["movements_id"],
                "message": "Movimiento actualizado exitosamente",
            },
            status=status.HTTP_200_OK,
        )
