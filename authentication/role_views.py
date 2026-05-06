import json
from datetime import datetime

from bson import ObjectId
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.custom_jwt import CustomJWTAuthentication
from user_queries.driver_database.mongo import Mongo

MODEL_TYPE_USER = "Mnemosine\\User"
ROLE_ADMIN_NAME = "Administrador"


def serialize_mongo(document):
    return json.loads(json.dumps(document, default=str))


def parse_object_id(value):
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


def parse_object_id_list(values):
    if not isinstance(values, list):
        return []
    parsed = []
    seen = set()
    for value in values:
        object_id = parse_object_id(value)
        if object_id and str(object_id) not in seen:
            parsed.append(object_id)
            seen.add(str(object_id))
    return parsed


def split_permission_name(permission_name):
    if not permission_name or "_" not in permission_name:
        return {"action": permission_name or "", "module": "general"}

    action, module = permission_name.split("_", 1)
    return {"action": action, "module": module}


def serialize_permission(permission):
    serialized = serialize_mongo(permission)
    serialized["id_str"] = serialized.get("_id")
    serialized.update(split_permission_name(permission.get("name")))
    return serialized


def serialize_role(role, permissions):
    serialized = serialize_mongo(role)
    serialized["id_str"] = serialized.get("_id")
    serialized["permissions"] = [serialize_permission(item) for item in permissions]
    serialized["permission_ids"] = [str(item["_id"]) for item in permissions]
    serialized["permission_names"] = [item.get("name") for item in permissions]
    return serialized


def serialize_user(user, roles, direct_permissions):
    serialized = serialize_mongo(user)
    serialized["id_str"] = serialized.get("_id")
    serialized["roles"] = [serialize_mongo(role) for role in roles]
    serialized["role_ids"] = [str(role["_id"]) for role in roles]
    serialized["role_names"] = [role.get("name") for role in roles]
    serialized["direct_permissions"] = [
        serialize_permission(item) for item in direct_permissions
    ]
    serialized["direct_permission_ids"] = [str(item["_id"]) for item in direct_permissions]
    serialized["direct_permission_names"] = [
        item.get("name") for item in direct_permissions
    ]
    return serialized


def build_permissions_by_module(permissions):
    grouped = {}
    for permission in permissions:
        serialized = serialize_permission(permission)
        module = serialized["module"]
        grouped.setdefault(module, []).append(serialized)

    ordered = []
    for module in sorted(grouped.keys()):
        ordered.append(
            {
                "module": module,
                "permissions": sorted(
                    grouped[module],
                    key=lambda item: (
                        {"ver": 0, "agregar": 1, "editar": 2, "eliminar": 3}.get(
                            item["action"], 9
                        ),
                        item["name"],
                    ),
                ),
            }
        )
    return ordered


def get_next_role_numeric_id(mongo):
    latest_role = mongo.connect("roles").find_one(
        {},
        sort=[("id", -1)],
        projection={"id": 1},
    )
    return int(latest_role.get("id", 0)) + 1 if latest_role else 1


def get_role_permissions_map(mongo, role_ids):
    if not role_ids:
        return {}

    role_permissions = list(
        mongo.connect("role_has_permissions").find({"role_id": {"$in": role_ids}})
    )
    permission_ids = [
        item["permission_id"]
        for item in role_permissions
        if isinstance(item.get("permission_id"), ObjectId)
    ]
    permissions = list(mongo.connect("permissions").find({"_id": {"$in": permission_ids}}))
    permission_map = {permission["_id"]: permission for permission in permissions}

    grouped = {}
    for relation in role_permissions:
        role_id = relation.get("role_id")
        permission = permission_map.get(relation.get("permission_id"))
        if not role_id or not permission:
            continue
        grouped.setdefault(role_id, []).append(permission)

    return grouped


def get_user_roles_and_permissions_map(mongo, user_ids):
    role_links = list(mongo.connect("user_has_roles").find({"model_id": {"$in": user_ids}}))
    direct_links = list(
        mongo.connect("user_has_permissions").find({"model_id": {"$in": user_ids}})
    )

    role_ids = [
        link["role_id"] for link in role_links if isinstance(link.get("role_id"), ObjectId)
    ]
    permission_ids = [
        link["permission_id"]
        for link in direct_links
        if isinstance(link.get("permission_id"), ObjectId)
    ]

    roles = list(mongo.connect("roles").find({"_id": {"$in": role_ids}}))
    permissions = list(
        mongo.connect("permissions").find({"_id": {"$in": permission_ids}})
    )

    role_map = {role["_id"]: role for role in roles}
    permission_map = {permission["_id"]: permission for permission in permissions}

    user_roles_map = {}
    for link in role_links:
        model_id = link.get("model_id")
        role = role_map.get(link.get("role_id"))
        if not model_id or not role:
            continue
        user_roles_map.setdefault(model_id, []).append(role)

    user_direct_permissions_map = {}
    for link in direct_links:
        model_id = link.get("model_id")
        permission = permission_map.get(link.get("permission_id"))
        if not model_id or not permission:
            continue
        user_direct_permissions_map.setdefault(model_id, []).append(permission)

    return user_roles_map, user_direct_permissions_map


class BaseRoleAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def get_mongo(self):
        return Mongo()


class RoleManageView(BaseRoleAPIView):
    def get(self, request):
        mongo = self.get_mongo()

        permissions = list(mongo.connect("permissions").find().sort("id", 1))
        roles = list(mongo.connect("roles").find().sort("id", 1))
        users = list(
            mongo.connect("authentication_my_user")
            .find({"deleted_at": None}, {"username": 1, "email": 1, "is_active": 1})
            .sort("username", 1)
        )

        role_ids = [role["_id"] for role in roles]
        user_ids = [user["_id"] for user in users]

        role_permissions_map = get_role_permissions_map(mongo, role_ids)
        user_roles_map, user_direct_permissions_map = get_user_roles_and_permissions_map(
            mongo, user_ids
        )

        return Response(
            {
                "roles": [
                    serialize_role(role, role_permissions_map.get(role["_id"], []))
                    for role in roles
                ],
                "permissions": [serialize_permission(permission) for permission in permissions],
                "permission_groups": build_permissions_by_module(permissions),
                "users": [
                    serialize_user(
                        user,
                        user_roles_map.get(user["_id"], []),
                        user_direct_permissions_map.get(user["_id"], []),
                    )
                    for user in users
                ],
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        mongo = self.get_mongo()
        name = (request.data.get("name") or "").strip()
        guard_name = (request.data.get("guard_name") or "web").strip() or "web"

        errors = {}
        if not name:
            errors["name"] = "El nombre es un campo requerido"
        elif mongo.connect("roles").find_one({"name": name}):
            errors["name"] = "Ya existe un rol con ese nombre"

        if errors:
            return Response(
                {"error": "Datos invalidos", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.utcnow()
        payload = {
            "_id": ObjectId(),
            "id": get_next_role_numeric_id(mongo),
            "name": name,
            "guard_name": guard_name,
            "created_at": now,
            "updated_at": now,
        }
        mongo.connect("roles").insert_one(payload)

        return Response(
            {"message": "Rol creado exitosamente", "role": serialize_mongo(payload)},
            status=status.HTTP_201_CREATED,
        )


class RolePermissionsDetailView(BaseRoleAPIView):
    def put(self, request, role_id):
        mongo = self.get_mongo()
        parsed_role_id = parse_object_id(role_id)
        if not parsed_role_id:
            return Response(
                {"error": "Rol invalido"}, status=status.HTTP_400_BAD_REQUEST
            )

        role = mongo.connect("roles").find_one({"_id": parsed_role_id})
        if not role:
            return Response(
                {"error": "Rol no encontrado"}, status=status.HTTP_404_NOT_FOUND
            )

        permission_ids = parse_object_id_list(request.data.get("permission_ids") or [])
        permissions = list(mongo.connect("permissions").find({"_id": {"$in": permission_ids}}))
        if len(permissions) != len(permission_ids):
            return Response(
                {"error": "Se recibieron permisos invalidos"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if role.get("name") == ROLE_ADMIN_NAME:
            return Response(
                {"error": "El rol Administrador es informativo y no se puede modificar"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        relation_collection = mongo.connect("role_has_permissions")
        relation_collection.delete_many({"role_id": parsed_role_id})
        if permission_ids:
            relation_collection.insert_many(
                [
                    {
                        "_id": ObjectId(),
                        "role_id": parsed_role_id,
                        "permission_id": permission_id,
                    }
                    for permission_id in permission_ids
                ]
            )

        mongo.connect("roles").update_one(
            {"_id": parsed_role_id},
            {"$set": {"updated_at": datetime.utcnow()}},
        )

        return Response(
            {"message": "Permisos del rol actualizados correctamente"},
            status=status.HTTP_200_OK,
        )


class UserRoleAccessDetailView(BaseRoleAPIView):
    def get_user(self, mongo, user_id):
        parsed_user_id = parse_object_id(user_id)
        if not parsed_user_id:
            return None
        return mongo.connect("authentication_my_user").find_one(
            {"_id": parsed_user_id, "deleted_at": None}
        )

    def get(self, request, user_id):
        mongo = self.get_mongo()
        user = self.get_user(mongo, user_id)
        if not user:
            return Response(
                {"error": "Usuario no encontrado"}, status=status.HTTP_404_NOT_FOUND
            )

        roles = list(mongo.connect("roles").find().sort("id", 1))
        permissions = list(mongo.connect("permissions").find().sort("id", 1))
        user_roles_map, user_direct_permissions_map = get_user_roles_and_permissions_map(
            mongo, [user["_id"]]
        )

        return Response(
            {
                "user": serialize_user(
                    user,
                    user_roles_map.get(user["_id"], []),
                    user_direct_permissions_map.get(user["_id"], []),
                ),
                "roles": [serialize_mongo(role) for role in roles],
                "permissions": [serialize_permission(permission) for permission in permissions],
                "permission_groups": build_permissions_by_module(permissions),
            },
            status=status.HTTP_200_OK,
        )

    def put(self, request, user_id):
        mongo = self.get_mongo()
        user = self.get_user(mongo, user_id)
        if not user:
            return Response(
                {"error": "Usuario no encontrado"}, status=status.HTTP_404_NOT_FOUND
            )

        role_ids = parse_object_id_list(request.data.get("role_ids") or [])
        permission_ids = parse_object_id_list(request.data.get("permission_ids") or [])

        roles = list(mongo.connect("roles").find({"_id": {"$in": role_ids}}))
        permissions = list(mongo.connect("permissions").find({"_id": {"$in": permission_ids}}))

        if len(roles) != len(role_ids):
            return Response(
                {"error": "Se recibieron roles invalidos"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(permissions) != len(permission_ids):
            return Response(
                {"error": "Se recibieron permisos invalidos"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_roles_collection = mongo.connect("user_has_roles")
        user_permissions_collection = mongo.connect("user_has_permissions")

        user_roles_collection.delete_many({"model_id": user["_id"]})
        if role_ids:
            user_roles_collection.insert_many(
                [
                    {
                        "_id": ObjectId(),
                        "role_id": role_id,
                        "model_type": MODEL_TYPE_USER,
                        "model_id": user["_id"],
                    }
                    for role_id in role_ids
                ]
            )

        user_permissions_collection.delete_many({"model_id": user["_id"]})
        if permission_ids:
            user_permissions_collection.insert_many(
                [
                    {
                        "_id": ObjectId(),
                        "permission_id": permission_id,
                        "model_type": MODEL_TYPE_USER,
                        "model_id": user["_id"],
                    }
                    for permission_id in permission_ids
                ]
            )

        return Response(
            {"message": "Accesos del usuario actualizados correctamente"},
            status=status.HTTP_200_OK,
        )
