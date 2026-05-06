from datetime import datetime

from bson import ObjectId
from rest_framework import status
from rest_framework.response import Response

from user_queries.shemas.catalog_elements_shema import (
    CatalogElementsSchema as CatalogElementSchema,
)
from user_queries.shemas.catalogs_shema import CatalogElementsSchema as CatalogSchema
from user_queries.shemas.genders_shema import GendersSchema
from user_queries.shemas.subgenders_shema import SubgendersSchema
from user_queries.views.movements.base import (
    BaseMovementAPIView,
    escape_search,
    parse_object_id,
    serialize_mongo,
)
from user_queries.views.tools import AuditManager


def serialize_entity(document):
    if not document:
        return None

    serialized = serialize_mongo(document)
    serialized["id"] = serialized.get("_id")
    return serialized


def build_text_query(search, fields):
    query = {"deleted_at": None}
    search_value = (search or "").strip()
    if search_value:
        regex = escape_search(search_value)
        query["$or"] = [{field: regex} for field in fields]
    return query


def get_title_description_payload(payload):
    return {
        "title": (payload.get("title") or "").strip(),
        "description": (payload.get("description") or "").strip() or None,
    }


def validate_title_payload(payload):
    errors = {}
    if not payload.get("title"):
        errors["title"] = "El titulo es un campo requerido"
    return errors


def validate_catalog_code(code):
    if not code:
        return "El codigo es un campo requerido"
    if len(code) < 2:
        return "El codigo debe contener al menos 2 caracteres"
    normalized = code.replace("_", "").replace("-", "")
    if not normalized.isalnum():
        return "El codigo solo puede contener letras, numeros, guion y guion bajo"
    return None


def validate_unique_field(collection, field_name, value, current_id=None, extra_query=None):
    if value in (None, ""):
        return False

    query = {field_name: value, "deleted_at": None}
    if extra_query:
        query.update(extra_query)
    if current_id:
        query["_id"] = {"$ne": current_id}
    return collection.find_one(query) is not None


class CatalogsView(BaseMovementAPIView):
    def get(self, request):
        mongo = self.get_mongo()
        query = build_text_query(request.query_params.get("search"), ["title", "description", "code"])
        catalogs = list(mongo.connect("catalogs").find(query).sort("title", 1))

        return Response(
            {"data": [serialize_entity(item) for item in catalogs]},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        mongo = self.get_mongo()
        catalog_data = get_title_description_payload(request.data)
        catalog_data["code"] = (request.data.get("code") or "").strip().lower()

        errors = validate_title_payload(catalog_data)
        code_error = validate_catalog_code(catalog_data["code"])
        if code_error:
            errors["code"] = code_error
        elif validate_unique_field(mongo.connect("catalogs"), "code", catalog_data["code"]):
            errors["code"] = "Ya existe un catalogo activo con ese codigo"

        if errors:
            return Response(
                {"error": "Datos invalidos", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        catalog_data = AuditManager().add_timestampsInfo(
            catalog_data, ObjectId(request.user.id)
        )
        catalog_payload = CatalogSchema(**catalog_data).model_dump(exclude_none=False)

        result = mongo.connect("catalogs").insert_one(catalog_payload)
        created = mongo.connect("catalogs").find_one({"_id": result.inserted_id})

        return Response(
            {
                "message": "Catalogo creado exitosamente",
                "catalog": serialize_entity(created),
            },
            status=status.HTTP_201_CREATED,
        )


class CatalogDetailView(BaseMovementAPIView):
    def get_catalog(self, mongo, catalog_id):
        parsed_id = parse_object_id(catalog_id)
        if not parsed_id:
            return None
        return mongo.connect("catalogs").find_one({"_id": parsed_id, "deleted_at": None})

    def get(self, request, id):
        mongo = self.get_mongo()
        catalog = self.get_catalog(mongo, id)

        if not catalog:
            return Response(
                {"error": "Catalogo no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {"catalog": serialize_entity(catalog)},
            status=status.HTTP_200_OK,
        )

    def put(self, request, id):
        mongo = self.get_mongo()
        catalog = self.get_catalog(mongo, id)

        if not catalog:
            return Response(
                {"error": "Catalogo no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        catalog_data = get_title_description_payload(request.data)
        catalog_data["code"] = (request.data.get("code") or "").strip().lower()

        errors = validate_title_payload(catalog_data)
        code_error = validate_catalog_code(catalog_data["code"])
        if code_error:
            errors["code"] = code_error
        elif validate_unique_field(
            mongo.connect("catalogs"),
            "code",
            catalog_data["code"],
            current_id=catalog["_id"],
        ):
            errors["code"] = "Ya existe un catalogo activo con ese codigo"

        if errors:
            return Response(
                {"error": "Datos invalidos", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        catalog_data["created_at"] = catalog.get("created_at")
        catalog_data["created_by"] = catalog.get("created_by")
        catalog_data["updated_at"] = catalog.get("updated_at")
        catalog_data["updated_by"] = catalog.get("updated_by")
        catalog_data["deleted_at"] = catalog.get("deleted_at")
        catalog_data["deleted_by"] = catalog.get("deleted_by")
        catalog_data = AuditManager().add_updateInfo(
            catalog_data, ObjectId(request.user.id)
        )
        catalog_payload = CatalogSchema(**catalog_data).model_dump(exclude_none=False)

        mongo.connect("catalogs").update_one(
            {"_id": catalog["_id"]},
            {"$set": catalog_payload},
        )
        updated = mongo.connect("catalogs").find_one({"_id": catalog["_id"]})

        return Response(
            {
                "message": "Catalogo actualizado exitosamente",
                "catalog": serialize_entity(updated),
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, id):
        mongo = self.get_mongo()
        catalog = self.get_catalog(mongo, id)

        if not catalog:
            return Response(
                {"error": "Catalogo no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        active_elements = mongo.connect("catalog_elements").count_documents(
            {"catalog_id": catalog["_id"], "deleted_at": None}
        )
        if active_elements:
            return Response(
                {
                    "error": "No se puede eliminar el catalogo mientras tenga elementos activos"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        mongo.connect("catalogs").update_one(
            {"_id": catalog["_id"]},
            {
                "$set": {
                    "deleted_at": datetime.now(AuditManager.tz),
                    "deleted_by": ObjectId(request.user.id),
                }
            },
        )

        return Response(
            {"message": "Catalogo eliminado exitosamente"},
            status=status.HTTP_200_OK,
        )


class CatalogElementsView(BaseMovementAPIView):
    def get_catalog(self, mongo, catalog_id):
        parsed_id = parse_object_id(catalog_id)
        if not parsed_id:
            return None
        return mongo.connect("catalogs").find_one({"_id": parsed_id, "deleted_at": None})

    def get(self, request, catalog_id):
        mongo = self.get_mongo()
        catalog = self.get_catalog(mongo, catalog_id)

        if not catalog:
            return Response(
                {"error": "Catalogo no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        query = build_text_query(request.query_params.get("search"), ["title", "description", "code"])
        query["catalog_id"] = catalog["_id"]
        elements = list(mongo.connect("catalog_elements").find(query).sort("title", 1))

        return Response(
            {
                "catalog": serialize_entity(catalog),
                "elements": [serialize_entity(item) for item in elements],
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, catalog_id):
        mongo = self.get_mongo()
        catalog = self.get_catalog(mongo, catalog_id)

        if not catalog:
            return Response(
                {"error": "Catalogo no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        element_data = get_title_description_payload(request.data)
        element_data["code"] = (request.data.get("code") or "").strip() or None
        element_data["catalog_id"] = catalog["_id"]

        errors = validate_title_payload(element_data)
        if element_data.get("code") and validate_unique_field(
            mongo.connect("catalog_elements"),
            "code",
            element_data["code"],
            extra_query={"catalog_id": catalog["_id"]},
        ):
            errors["code"] = "Ya existe un elemento activo con ese codigo en el catalogo"

        if errors:
            return Response(
                {"error": "Datos invalidos", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        element_data = AuditManager().add_timestampsInfo(
            element_data, ObjectId(request.user.id)
        )
        element_payload = CatalogElementSchema(**element_data).model_dump(exclude_none=False)

        result = mongo.connect("catalog_elements").insert_one(element_payload)
        created = mongo.connect("catalog_elements").find_one({"_id": result.inserted_id})

        return Response(
            {
                "message": "Elemento creado exitosamente",
                "element": serialize_entity(created),
            },
            status=status.HTTP_201_CREATED,
        )


class CatalogElementDetailView(BaseMovementAPIView):
    def get_element(self, mongo, element_id):
        parsed_id = parse_object_id(element_id)
        if not parsed_id:
            return None
        return mongo.connect("catalog_elements").find_one(
            {"_id": parsed_id, "deleted_at": None}
        )

    def get(self, request, id):
        mongo = self.get_mongo()
        element = self.get_element(mongo, id)

        if not element:
            return Response(
                {"error": "Elemento no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        catalog = mongo.connect("catalogs").find_one({"_id": element["catalog_id"]})
        return Response(
            {
                "element": serialize_entity(element),
                "catalog": serialize_entity(catalog),
            },
            status=status.HTTP_200_OK,
        )

    def put(self, request, id):
        mongo = self.get_mongo()
        element = self.get_element(mongo, id)

        if not element:
            return Response(
                {"error": "Elemento no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        element_data = get_title_description_payload(request.data)
        element_data["code"] = (request.data.get("code") or "").strip() or None
        element_data["catalog_id"] = element["catalog_id"]

        errors = validate_title_payload(element_data)
        if element_data.get("code") and validate_unique_field(
            mongo.connect("catalog_elements"),
            "code",
            element_data["code"],
            current_id=element["_id"],
            extra_query={"catalog_id": element["catalog_id"]},
        ):
            errors["code"] = "Ya existe un elemento activo con ese codigo en el catalogo"

        if errors:
            return Response(
                {"error": "Datos invalidos", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        element_data["created_at"] = element.get("created_at")
        element_data["created_by"] = element.get("created_by")
        element_data["updated_at"] = element.get("updated_at")
        element_data["updated_by"] = element.get("updated_by")
        element_data["deleted_at"] = element.get("deleted_at")
        element_data["deleted_by"] = element.get("deleted_by")
        element_data = AuditManager().add_updateInfo(
            element_data, ObjectId(request.user.id)
        )
        element_payload = CatalogElementSchema(**element_data).model_dump(exclude_none=False)

        mongo.connect("catalog_elements").update_one(
            {"_id": element["_id"]},
            {"$set": element_payload},
        )
        updated = mongo.connect("catalog_elements").find_one({"_id": element["_id"]})

        return Response(
            {
                "message": "Elemento actualizado exitosamente",
                "element": serialize_entity(updated),
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, id):
        mongo = self.get_mongo()
        element = self.get_element(mongo, id)

        if not element:
            return Response(
                {"error": "Elemento no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        mongo.connect("catalog_elements").update_one(
            {"_id": element["_id"]},
            {
                "$set": {
                    "deleted_at": datetime.now(AuditManager.tz),
                    "deleted_by": ObjectId(request.user.id),
                }
            },
        )

        return Response(
            {"message": "Elemento eliminado exitosamente"},
            status=status.HTTP_200_OK,
        )


class GendersView(BaseMovementAPIView):
    def get(self, request):
        mongo = self.get_mongo()
        query = build_text_query(request.query_params.get("search"), ["title", "description"])
        genders = list(mongo.connect("genders").find(query).sort("title", 1))

        return Response(
            {"data": [serialize_entity(item) for item in genders]},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        mongo = self.get_mongo()
        gender_data = get_title_description_payload(request.data)
        errors = validate_title_payload(gender_data)

        if validate_unique_field(mongo.connect("genders"), "title", gender_data["title"]):
            errors["title"] = "Ya existe un genero activo con ese titulo"

        if errors:
            return Response(
                {"error": "Datos invalidos", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        gender_data = AuditManager().add_timestampsInfo(
            gender_data, ObjectId(request.user.id)
        )
        gender_payload = GendersSchema(**gender_data).model_dump(exclude_none=False)

        result = mongo.connect("genders").insert_one(gender_payload)
        created = mongo.connect("genders").find_one({"_id": result.inserted_id})

        return Response(
            {"message": "Genero creado exitosamente", "gender": serialize_entity(created)},
            status=status.HTTP_201_CREATED,
        )


class GenderDetailView(BaseMovementAPIView):
    def get_gender(self, mongo, gender_id):
        parsed_id = parse_object_id(gender_id)
        if not parsed_id:
            return None
        return mongo.connect("genders").find_one({"_id": parsed_id, "deleted_at": None})

    def get(self, request, id):
        mongo = self.get_mongo()
        gender = self.get_gender(mongo, id)

        if not gender:
            return Response(
                {"error": "Genero no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {"gender": serialize_entity(gender)},
            status=status.HTTP_200_OK,
        )

    def put(self, request, id):
        mongo = self.get_mongo()
        gender = self.get_gender(mongo, id)

        if not gender:
            return Response(
                {"error": "Genero no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        gender_data = get_title_description_payload(request.data)
        errors = validate_title_payload(gender_data)

        if validate_unique_field(
            mongo.connect("genders"),
            "title",
            gender_data["title"],
            current_id=gender["_id"],
        ):
            errors["title"] = "Ya existe un genero activo con ese titulo"

        if errors:
            return Response(
                {"error": "Datos invalidos", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        gender_data["created_at"] = gender.get("created_at")
        gender_data["created_by"] = gender.get("created_by")
        gender_data["updated_at"] = gender.get("updated_at")
        gender_data["updated_by"] = gender.get("updated_by")
        gender_data["deleted_at"] = gender.get("deleted_at")
        gender_data["deleted_by"] = gender.get("deleted_by")
        gender_data = AuditManager().add_updateInfo(
            gender_data, ObjectId(request.user.id)
        )
        gender_payload = GendersSchema(**gender_data).model_dump(exclude_none=False)

        mongo.connect("genders").update_one(
            {"_id": gender["_id"]},
            {"$set": gender_payload},
        )
        updated = mongo.connect("genders").find_one({"_id": gender["_id"]})

        return Response(
            {
                "message": "Genero actualizado exitosamente",
                "gender": serialize_entity(updated),
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, id):
        mongo = self.get_mongo()
        gender = self.get_gender(mongo, id)

        if not gender:
            return Response(
                {"error": "Genero no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        active_subgenders = mongo.connect("subgenders").count_documents(
            {"gender_id": gender["_id"], "deleted_at": None}
        )
        if active_subgenders:
            return Response(
                {
                    "error": "No se puede eliminar el genero mientras tenga subgeneros activos"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        mongo.connect("genders").update_one(
            {"_id": gender["_id"]},
            {
                "$set": {
                    "deleted_at": datetime.now(AuditManager.tz),
                    "deleted_by": ObjectId(request.user.id),
                }
            },
        )

        return Response(
            {"message": "Genero eliminado exitosamente"},
            status=status.HTTP_200_OK,
        )


class SubgendersView(BaseMovementAPIView):
    def get_gender(self, mongo, gender_id):
        parsed_id = parse_object_id(gender_id)
        if not parsed_id:
            return None
        return mongo.connect("genders").find_one({"_id": parsed_id, "deleted_at": None})

    def get(self, request, gender_id):
        mongo = self.get_mongo()
        gender = self.get_gender(mongo, gender_id)

        if not gender:
            return Response(
                {"error": "Genero no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        query = build_text_query(request.query_params.get("search"), ["title", "description"])
        query["gender_id"] = gender["_id"]
        subgenders = list(mongo.connect("subgenders").find(query).sort("title", 1))

        return Response(
            {
                "gender": serialize_entity(gender),
                "subgenders": [serialize_entity(item) for item in subgenders],
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, gender_id):
        mongo = self.get_mongo()
        gender = self.get_gender(mongo, gender_id)

        if not gender:
            return Response(
                {"error": "Genero no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        subgender_data = get_title_description_payload(request.data)
        subgender_data["gender_id"] = gender["_id"]
        errors = validate_title_payload(subgender_data)

        if validate_unique_field(
            mongo.connect("subgenders"),
            "title",
            subgender_data["title"],
            extra_query={"gender_id": gender["_id"]},
        ):
            errors["title"] = "Ya existe un subgenero activo con ese titulo para este genero"

        if errors:
            return Response(
                {"error": "Datos invalidos", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subgender_data = AuditManager().add_timestampsInfo(
            subgender_data, ObjectId(request.user.id)
        )
        subgender_payload = SubgendersSchema(**subgender_data).model_dump(exclude_none=False)

        result = mongo.connect("subgenders").insert_one(subgender_payload)
        created = mongo.connect("subgenders").find_one({"_id": result.inserted_id})

        return Response(
            {
                "message": "Subgenero creado exitosamente",
                "subgender": serialize_entity(created),
            },
            status=status.HTTP_201_CREATED,
        )


class SubgenderDetailView(BaseMovementAPIView):
    def get_subgender(self, mongo, subgender_id):
        parsed_id = parse_object_id(subgender_id)
        if not parsed_id:
            return None
        return mongo.connect("subgenders").find_one(
            {"_id": parsed_id, "deleted_at": None}
        )

    def get(self, request, id):
        mongo = self.get_mongo()
        subgender = self.get_subgender(mongo, id)

        if not subgender:
            return Response(
                {"error": "Subgenero no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        gender = mongo.connect("genders").find_one({"_id": subgender["gender_id"]})
        return Response(
            {
                "subgender": serialize_entity(subgender),
                "gender": serialize_entity(gender),
            },
            status=status.HTTP_200_OK,
        )

    def put(self, request, id):
        mongo = self.get_mongo()
        subgender = self.get_subgender(mongo, id)

        if not subgender:
            return Response(
                {"error": "Subgenero no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        subgender_data = get_title_description_payload(request.data)
        subgender_data["gender_id"] = subgender["gender_id"]
        errors = validate_title_payload(subgender_data)

        if validate_unique_field(
            mongo.connect("subgenders"),
            "title",
            subgender_data["title"],
            current_id=subgender["_id"],
            extra_query={"gender_id": subgender["gender_id"]},
        ):
            errors["title"] = "Ya existe un subgenero activo con ese titulo para este genero"

        if errors:
            return Response(
                {"error": "Datos invalidos", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subgender_data["created_at"] = subgender.get("created_at")
        subgender_data["created_by"] = subgender.get("created_by")
        subgender_data["updated_at"] = subgender.get("updated_at")
        subgender_data["updated_by"] = subgender.get("updated_by")
        subgender_data["deleted_at"] = subgender.get("deleted_at")
        subgender_data["deleted_by"] = subgender.get("deleted_by")
        subgender_data = AuditManager().add_updateInfo(
            subgender_data, ObjectId(request.user.id)
        )
        subgender_payload = SubgendersSchema(**subgender_data).model_dump(exclude_none=False)

        mongo.connect("subgenders").update_one(
            {"_id": subgender["_id"]},
            {"$set": subgender_payload},
        )
        updated = mongo.connect("subgenders").find_one({"_id": subgender["_id"]})

        return Response(
            {
                "message": "Subgenero actualizado exitosamente",
                "subgender": serialize_entity(updated),
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, id):
        mongo = self.get_mongo()
        subgender = self.get_subgender(mongo, id)

        if not subgender:
            return Response(
                {"error": "Subgenero no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        mongo.connect("subgenders").update_one(
            {"_id": subgender["_id"]},
            {
                "$set": {
                    "deleted_at": datetime.now(AuditManager.tz),
                    "deleted_by": ObjectId(request.user.id),
                }
            },
        )

        return Response(
            {"message": "Subgenero eliminado exitosamente"},
            status=status.HTTP_200_OK,
        )
