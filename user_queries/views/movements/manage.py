from rest_framework import status
from rest_framework.response import Response

from .base import BaseMovementAPIView, escape_search


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
            regex = escape_search(search)
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

            if (
                not exhibition_ids
                and not institution_ids
                and not piece_ids
                and not search.isdigit()
            ):
                return Response(
                    {"data": [], "page": page, "per_page": per_page, "total": 0},
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
        documents = list(
            movements_collection.find(query)
            .sort("movements_id", -1)
            .skip(skip)
            .limit(per_page)
        )

        doc_exhibition_ids = list(
            {doc.get("exhibition_id") for doc in documents if doc.get("exhibition_id")}
        )
        missing_exhibition_ids = [
            exhibition_id
            for exhibition_id in doc_exhibition_ids
            if exhibition_id not in exhibitions_map
        ]

        if missing_exhibition_ids:
            for exhibition in mongo.connect("exhibitions").find(
                {"_id": {"$in": missing_exhibition_ids}}, {"name": 1}
            ):
                exhibitions_map[exhibition["_id"]] = exhibition["name"]

        all_institution_ids = {
            institution_id
            for doc in documents
            for institution_id in doc.get("institution_ids", [])
        }
        missing_institution_ids = [
            institution_id
            for institution_id in all_institution_ids
            if institution_id not in institutions_map
        ]

        if missing_institution_ids:
            for institution in mongo.connect("institutions").find(
                {"_id": {"$in": list(missing_institution_ids)}}, {"name": 1}
            ):
                institutions_map[institution["_id"]] = institution["name"]

        all_piece_ids = {
            piece_id for doc in documents for piece_id in (doc.get("pieces_ids") or [])
        }
        pieces_map = {}
        if all_piece_ids:
            pieces_map = {
                piece["_id"]: piece["catalog_number"]
                for piece in mongo.connect("pieces").find(
                    {"_id": {"$in": list(all_piece_ids)}}, {"catalog_number": 1}
                )
            }

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
