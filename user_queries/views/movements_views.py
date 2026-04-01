import json
import re
import time

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.custom_jwt import CustomJWTAuthentication
from user_queries.driver_database.mongo import Mongo


class MovementsManage(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def get(self, request):

        mongo = Mongo()

        page = int(request.query_params.get("page", 1))
        per_page = int(request.query_params.get("per_page", 10))
        search = request.query_params.get("search", "")

        skip = (page - 1) * per_page
        query = {}

        exhibitions_map = {}
        institutions_map = {}

        # 🔎 Búsqueda
        if search:
            regex = (
                {"$regex": f"{re.escape(search)}", "$options": "i"}
                if search
                else {"$regex": f"{search}", "$options": "i"}
            )
            # buscar exhibitions
            exhibitions_cursor = mongo.connect("exhibitions").find(
                {"name": regex, "deleted_at": None}, {"_id": 1, "name": 1}
            )
            # hacemos un list del cursor
            exhibitions = list(exhibitions_cursor)
            # extraemos los ids
            exhibition_ids = [e["_id"] for e in exhibitions]
            # mapear id a name
            exhibitions_map = {e["_id"]: e["name"] for e in exhibitions}
            # buscar institutions
            institutions_cursor = mongo.connect("institutions").find(
                {"name": regex, "deleted_at": None}, {"_id": 1, "name": 1}
            )
            # hacemos un list del cursor
            institutions = list(institutions_cursor)
            # extraemos los ids
            institution_ids = [i["_id"] for i in institutions]
            # mapear id a name
            institutions_map = {i["_id"]: i["name"] for i in institutions}

            # buscar pieces
            pieces_cursor = mongo.connect("pieces").find(
                {"catalog_number": regex, "deleted_at": None},
                {"_id": 1, "catalog_number": 1},
            )

            # hacemos un list del cursor
            pieces = list(pieces_cursor)
            # extraemos los ids
            piece_ids = [p["_id"] for p in pieces]
            # mapear id a name
            pieces_map = {p["_id"]: p["catalog_number"] for p in pieces}
            # Si no se encontró nada, devolver respuesta vacía
            # Early return para evitar hacer consultas innecesarias a movements
            if (
                not exhibition_ids
                and not institution_ids
                and not piece_ids
                and not search.isdigit()
            ):
                print("Early Return")
                return Response(
                    {
                        "data": [],
                        "page": page,
                        "per_page": per_page,
                        "total": 0,
                    },
                    status=status.HTTP_200_OK,
                )

            # query para movements
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

        # 📊 total
        total = movements_collection.count_documents(query)

        # 📦 movimientos paginados
        cursor = (
            movements_collection.find(query)
            .sort("movements_id", -1)
            .skip(skip)
            .limit(per_page)
        )

        documents = list(cursor)

        # -------------------------------------------------
        # Resolver exhibitions si no hubo búsqueda
        # -------------------------------------------------

        # SIEMPRE asegurar que tienes todos los exhibition_ids
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

            for e in exhibitions_cursor:
                exhibitions_map[e["_id"]] = e["name"]

        # -------------------------------------------------
        # Resolver institutions
        # -------------------------------------------------

        all_institution_ids = set()

        for doc in documents:
            for iid in doc.get("institution_ids", []):
                all_institution_ids.add(iid)

        missing_institution_ids = [
            iid for iid in all_institution_ids if iid not in institutions_map
        ]

        if missing_institution_ids:
            institutions_cursor = mongo.connect("institutions").find(
                {"_id": {"$in": list(missing_institution_ids)}}, {"name": 1}
            )

            for i in institutions_cursor:
                institutions_map[i["_id"]] = i["name"]

        # -------------------------------------------------
        # Resolver pieces
        # -------------------------------------------------

        pieces_map = {}
        all_pieces_ids = set()
        for doc in documents:
            if doc.get("pieces_ids"):
                for pieces_id in doc.get("pieces_ids", []):
                    all_pieces_ids.add(pieces_id)

        if all_pieces_ids:
            pieces_cursor = mongo.connect("pieces").find(
                {"_id": {"$in": list(all_pieces_ids)}}, {"catalog_number": 1}
            )

            pieces_map = {p["_id"]: p["catalog_number"] for p in pieces_cursor}

        # -------------------------------------------------
        # Construir respuesta
        # -------------------------------------------------
        # print("documents",documents)
        # print("exhibitions_map", exhibitions_map)
        # for mov in documents:
        #   for k, v in mov.items():
        #       if "ObjectId" in str(type(v)):
        #           print("🔥 Campo con ObjectId:", k, v)

        movements_data = [
            {
                "id": int(mov["movements_id"]),
                "departure_date": mov.get("departure_date"),
                "exhibition_name": exhibitions_map.get(mov.get("exhibition_id")),
                "institution_names": ", ".join(
                    institutions_map[iid]
                    for iid in mov.get("institution_ids") or []
                    if iid in institutions_map
                ),
                "pieces": ", ".join(
                    pieces_map[pid]
                    for pid in (mov.get("pieces_ids") or [])
                    if pid in pieces_map
                ),
                "pieces_count": len(
                    set(str(pid) for pid in (mov.get("pieces_ids") or []))
                    - set(str(pid) for pid in (mov.get("pieces_ids_arrived") or []))
                ),
                # 👇 estos eran los que te rompían todo
                "authorized_by_movements": str(mov.get("authorized_by_movements"))
                if mov.get("authorized_by_movements")
                else None,
                "itinerant": mov.get("itinerant"),
            }
            for mov in documents
        ]

        """
        pieces_ids = mov.get("pieces_ids") or []
        pieces_ids_arrived = mov.get("pieces_ids_arrived") or []
        pieces_count = len(set(pieces_ids) - set(pieces_ids_arrived))

        """

        return Response(
            {
                "data": movements_data,
                "page": page,
                "per_page": per_page,
                "total": total,
            },
            status=status.HTTP_200_OK,
        )
