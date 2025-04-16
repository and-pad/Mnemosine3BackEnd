import json
from turtle import title
from bson import ObjectId
from collections import defaultdict
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from user_queries.driver_database.mongo import Mongo
from user_queries.mongo_queries import research_edit


class ResearchEdit(APIView):

    def get_module_id(self, module_name, mongo):
        """Obtiene el ID de un módulo por su nombre."""
        module = mongo.connect("modules").find_one(
            {"name": module_name, "deleted_at": None}, {"_id": 1}
        )
        return module["_id"] if module else None

    def get_genders(self, mongo):
        """Obtiene todos los géneros en una sola consulta."""
        genders = mongo.connect("genders").find({"deleted_at": None}, {"title": 1})
        if not genders:
            return []

        genders = list(genders)
        return self.serialize_mongo_data(genders)

    def get_subgenders(self, mongo):
        """Obtiene todos los subgéneros en una sola consulta."""
        subgenders = mongo.connect("subgenders").find(
            {"deleted_at": None}, {"title": 1, "gender_id": 1}
        )
        if not subgenders:
            return []

        subgenders = list(subgenders)
        return self.serialize_mongo_data(subgenders)

    def get(self, request, _id):
        mongo = Mongo()
        module_id = self.get_module_id("research", mongo)
        if not module_id:
            return Response(
                {"response": "Módulo no encontrado"}, status=status.HTTP_400_BAD_REQUEST
            )

        research = list(
            mongo.connect("researchs").aggregate(research_edit(module_id, _id))
        )
        if not research:
            return Response(
                {"response": "No se encontraron registros"},
                status=status.HTTP_404_NOT_FOUND,
            )

        print("research", research[0]["inventory_data"])
        cursor_change_json = json.loads(json.dumps(research, default=str))[0]

        # Obtener todos los catálogos en una sola consulta
        catalog_codes = ["author", "involved_creation", "place_of_creation", "period"]
        catalog_ids = self.get_catalog_ids(mongo, catalog_codes)
        all_catalogs = {
            code: self.get_catalog_elements(mongo, catalog_id)
            for code, catalog_id in catalog_ids.items()
        }

        # Obtener datos de los campos relacionados
        author_research = cursor_change_json.get("authors_info", [])
        """self.get_research_data(
            mongo, cursor_change_json, "author_ids"
        )"""
        print("author_research", author_research)
        involved_creation_research = cursor_change_json.get(
            "involved_creation_info", []
        )
        """
        self.get_research_data(
            mongo, cursor_change_json, "involved_creation_ids"
        )
        """
        print("involved_creation_research", involved_creation_research)
        place_of_creation_research = cursor_change_json.get(
            "place_of_creation_info", []
        )
        """
        self.get_research_data(
            mongo, cursor_change_json, "place_of_creation_id"
        )
        """
        print("place_of_creation_research", place_of_creation_research)
        #period_research = self.get_research_data(mongo, cursor_change_json, "period_id")

        # catalogs = all_catalogs.get("author", [])

        # for catalog in catalogs:
        # print("period_research", catalog.get("title", ""))

        catalog_code = ["object_type", "dominant_material"]
        catalog_ids = self.get_catalog_ids(mongo, catalog_code)

        all_object_type = {
            code: self.get_catalog_elements(mongo, catalog_id)
            for code, catalog_id in catalog_ids.items()
        }

        researchs_documents = mongo.connect("documents").find(
            {"piece_id": ObjectId(_id), "deleted_at": None, "module_id": module_id}
        )
        researchs_documents = list(researchs_documents)
        cursor_change_json["documents"] = self.serialize_mongo_data(researchs_documents)

        researchs_photos = mongo.connect("photographs").find(
            {"piece_id": ObjectId(_id), "deleted_at": None, "module_id": module_id}
        )
        researchs_photos = list(researchs_photos)
        cursor_change_json["photos"] = self.serialize_mongo_data(researchs_photos)

        # print("all_object_type",all_object_type.get("dominant_material", []))
        #print("period",period_research)
        return Response(
            {
                "research_data": cursor_change_json,
                # "author_research": author_research,
                # "involved_creation_research": involved_creation_research,
                # "place_of_creation_research": place_of_creation_research,
                #"period_research": period_research,
                "all_authors": all_catalogs.get("author", []),
                "all_involved_creation": all_catalogs.get("involved_creation", []),
                "all_place_of_creation": all_catalogs.get("place_of_creation", []),
                "all_period": all_catalogs.get("period", []),
                "all_genders": self.get_genders(mongo),
                "all_subgenders": self.get_subgenders(mongo),
                "all_object_type": all_object_type.get("object_type", []),
                "all_dominant_material": all_object_type.get("dominant_material", []),
            },
            status=status.HTTP_200_OK,
        )

    def get_catalog_ids(self, mongo, catalog_codes):
        """Obtiene los ObjectId de los catálogos en una sola consulta."""
        catalogs = mongo.connect("catalogs").find(
            {"code": {"$in": catalog_codes}, "deleted_at": None}, {"code": 1, "_id": 1}
        )
        return {cat["code"]: cat["_id"] for cat in catalogs}

    def get_catalog_elements(self, mongo, catalog_id):
        """Obtiene todos los elementos de un catálogo por su ObjectId."""
        if not catalog_id:
            return []
        elements = list(
            mongo.connect("catalog_elements").find(
                {"catalog_id": ObjectId(catalog_id), "deleted_at": None}, {"title": 1}
            )
        )
        return self.serialize_mongo_data(elements)

    def get_research_data(self, mongo, data, field):
        """Obtiene los datos relacionados a un campo específico del research."""
        ids = data.get(field, [])
        if not isinstance(ids, list) or not ids:
            return []

        # Consulta optimizada para traer todos los elementos en una sola búsqueda
        elements = list(
            mongo.connect("catalog_elements").find(
                {"_id": {"$in": [ObjectId(i) for i in ids if ObjectId.is_valid(i)]}},
                {"_id": 1, "title": 1},
            )
        )
        return self.serialize_mongo_data(elements)

    def serialize_mongo_data(self, data):
        """Serializa datos de MongoDB a JSON serializable."""
        return json.loads(json.dumps(data, default=str))
