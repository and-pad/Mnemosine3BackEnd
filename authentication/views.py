# Create your views here.
# import json
import logging
from time import time

import jwt
from bson import ObjectId
from pymongo import ReturnDocument

# from django.contrib.auth.models import User
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import make_password
from rest_framework import serializers, status

# from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# from rest_framework_simplejwt.authentication import JWTAuthentication
from authentication.custom_jwt import CustomJWTAuthentication
from authentication.user_documents import (
    LEGACY_USER_COUNTER_ID,
    USER_COUNTER_COLLECTION,
    USER_COUNTER_KEY,
    build_user_collection_query,
    get_user_lookup_ids,
    get_user_username,
    normalize_user_document,
)
from user_queries.driver_database.mongo import Mongo

# from django.shortcuts import get_object_or_404
from .mongo_queries import getPermissions

User = get_user_model()
logger = logging.getLogger(__name__)


SECRET = "Ax100_2022_xLk8optaeqna9d5WdAfCeeGdLk84YgDe"
ACCESS_LIFETIME = 60 * 60 * 4  # 4 horas
REFRESH_LIFETIME = 60 * 60 * 24  # 24 horas


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):

        email = data.get("email")
        password = data.get("password")

        authenticated_user = authenticate(username=email, password=password)

        if authenticated_user:
            if authenticated_user.is_active:
                data["user"] = authenticated_user
                return data
            else:
                raise serializers.ValidationError(
                    "La cuenta del usuario está desactivada."
                )
        else:
            raise serializers.ValidationError(
                "No se pudo autenticar al usuario con las credenciales proporcionadas."
            )


class Permission:
    def get_permission(self, user):
        mongo = Mongo()

        collection = mongo.connect("user_has_roles")
        cursor = collection.aggregate(getPermissions(user))

        # Almacenar el resultado en una lista
        results = list(cursor)
        for item in results:
            permissions_info = item["permissions_info"]
            overwrite_permissions_info = item["overwrite_permissions_info"]
            for overwrite_perm in overwrite_permissions_info:
                # Verificar si el permiso ya existe
                for i, perm in enumerate(permissions_info):
                    if perm["id"] == overwrite_perm["id"]:
                        permissions_info[i] = overwrite_perm  # Sobrescribir
                        break
                    else:
                        if overwrite_perm not in permissions_info:
                            permissions_info.append(
                                overwrite_perm
                            )  # Agregar si no existe

            names = [perm["name"] for perm in permissions_info]

            # names = ['ver_usuarios', 'ver_roles', 'ver_catalogos', 'ver_configuraciones']
            # print(names)
            return names


class signinView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        # Validar login como ya lo haces tú
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=401)

        user = serializer.validated_data["user"]
        user_id = str(user.id)  # ya es Mongo

        # === GENERAR ACCESS TOKEN ===
        access = jwt.encode(
            {"user_id": user_id, "exp": int(time()) + ACCESS_LIFETIME},
            SECRET,
            algorithm="HS256",
        )

        # === GENERAR REFRESH TOKEN ===
        refresh = jwt.encode(
            {"user_id": user_id, "exp": int(time()) + REFRESH_LIFETIME},
            SECRET,
            algorithm="HS256",
        )

        permission = Permission()
        user_permissions = permission.get_permission(user)

        return Response(
            {
                "refresh": refresh,
                "access": access,
                "user": getattr(user, "username", "") or getattr(user, "email", ""),
                "permissions": user_permissions,
            },
            status=202,
        )

    # ================================
    # REFRESCAR ACCESS TOKEN
    # ================================

    def put(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response({"error": "Se requiere un refresh token"}, status=400)

        try:
            payload = jwt.decode(refresh, SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return Response({"error": "Refresh expirado"}, status=401)
        except Exception:
            return Response({"error": "Token inválido"}, status=401)

        user_id = payload["user_id"]
        print("user_id", user_id)
        # Buscar usuario en Mongo
        mongo = Mongo()
        collection = mongo.connect("authentication_my_user")
        user_doc = collection.find_one({"_id": ObjectId(user_id), "deleted_at": None})
        print("user_doc", user_doc)
        if not user_doc:
            return Response({"error": "Usuario no encontrado"}, status=404)

        # Crear access nuevo
        new_access = jwt.encode(
            {"user_id": user_id, "exp": int(time()) + ACCESS_LIFETIME},
            SECRET,
            algorithm="HS256",
        )

        # Permisos
        permission = Permission()
        user_permissions = permission.get_permission(user_doc)

        return Response(
            {
                "access": new_access,
                "user": get_user_username(user_doc),
                "permissions": user_permissions,
            }
        )


class SignupSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField()
    id = serializers.IntegerField()

    def create(self, validated_data):
        mongo = Mongo()
        collection = mongo.connect("authentication_my_user")

        # Hasheamos la contraseña igual que Django hace
        hashed_password = make_password(validated_data["password"])

        user_doc = {
            "_id": ObjectId(),  # Mongo ObjectId
            "id": validated_data["id"],  # tu ID incremental
            "username": validated_data["username"],
            "email": validated_data["email"],
            "password": hashed_password,
            "is_active": True,
            "is_staff": False,
            "is_superuser": False,
            "deleted_at": None,
        }

        # Insertar directamente en Mongo
        collection.insert_one(user_doc)

        # Opcional: devolver un objeto tipo User de Django para compatibilidad
        user = User(
            id=validated_data["id"],
            username=validated_data["username"],
            email=validated_data["email"],
            password=hashed_password,
            is_active=True,
            is_staff=False,
            is_superuser=False,
            deleted_at=None,
        )

        return user


class InactiveUser(APIView):
    permission_classes = [IsAuthenticated]

    authentication_classes = [CustomJWTAuthentication]

    def patch(self, request):

        try:
            user_id = request.data.get("user_id")
            if not user_id:
                return Response(
                    {"error": "Se requiere user_id"}, status=status.HTTP_400_BAD_REQUEST
                )

            mongo = Mongo()
            users_collection = mongo.connect("authentication_my_user")

            result = users_collection.update_one(
                {"_id": ObjectId(user_id)}, {"$set": {"is_active": False}}
            )

            if result.matched_count == 0:
                return Response(
                    {"error": "Usuario no encontrado"}, status=status.HTTP_404_NOT_FOUND
                )

            return Response(
                {"response": "record_changed"}, status=status.HTTP_202_ACCEPTED
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ActivateUser(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def patch(self, request):
        try:
            user_id = request.data.get("user_id")
            if not user_id:
                return Response(
                    {"error": "Se requiere user_id"}, status=status.HTTP_400_BAD_REQUEST
                )

            mongo = Mongo()
            users_collection = mongo.connect("authentication_my_user")

            result = users_collection.update_one(
                {"_id": ObjectId(user_id)}, {"$set": {"is_active": True}}
            )

            if result.matched_count == 0:
                return Response(
                    {"error": "Usuario no encontrado"}, status=status.HTTP_404_NOT_FOUND
                )

            return Response(
                {"response": "record_changed"}, status=status.HTTP_202_ACCEPTED
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class EditUser(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def patch(self, request):
        try:
            data = request.data.get("formDataChange")
            user_id = data.get("user_id")
            if not user_id:
                return Response(
                    {"error": "Se requiere user_id"}, status=status.HTTP_400_BAD_REQUEST
                )

            mongo = Mongo()
            users_collection = mongo.connect("authentication_my_user")
            user = users_collection.find_one({"_id": ObjectId(user_id)})

            if not user:
                return Response(
                    {"error": "Usuario no encontrado"}, status=status.HTTP_404_NOT_FOUND
                )

            # Actualizar campos básicos
            update_fields = {}
            if "user" in data:
                update_fields["username"] = data["user"]
            if "email" in data:
                update_fields["email"] = data["email"]
            if "password" in data and data["password"]:
                # Hashear la contraseña usando el mismo método que Django
                update_fields["password"] = make_password(data["password"])

            if update_fields:
                users_collection.update_one(
                    {"_id": ObjectId(user_id)}, {"$set": update_fields}
                )

            # Actualizar rol
            rol_name = data.get("rol")
            rol_id = data.get("rol_id")
            if rol_id is not None:
                user_roles_collection = mongo.connect("user_has_roles")
                current_role = user_roles_collection.find_one(
                    {"model_id": str(user_id)}
                )

                if not current_role or current_role.get("role_id") != int(rol_id):
                    roles_collection = mongo.connect("roles")
                    role_doc = roles_collection.find_one({"id": int(rol_id)})
                    if not role_doc or role_doc.get("name") != rol_name:
                        return Response(
                            {"error": "El rol no coincide con el id"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    user_roles_collection.update_one(
                        {"model_id": str(user_id)},
                        {"$set": {"role_id": int(rol_id)}},
                        upsert=True,
                    )

            return Response(
                {"response": "user_updated"}, status=status.HTTP_202_ACCEPTED
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class DeleteUser(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def delete(self, request):
        try:
            user_id = request.data.get("user_id")
            if not user_id:
                return Response(
                    {"error": "Se requiere user_id"}, status=status.HTTP_400_BAD_REQUEST
                )

            mongo = Mongo()
            users_collection = mongo.connect("authentication_my_user")
            user = users_collection.find_one({"_id": ObjectId(user_id)})

            if not user:
                return Response(
                    {"error": "Usuario no encontrado"}, status=status.HTTP_404_NOT_FOUND
                )

            # Guardar en deleted_auth_users
            deleted_collection = mongo.connect("deleted_auth_users")
            deleted_collection.insert_one(user)

            # Borrar usuario
            users_collection.delete_one({"_id": ObjectId(user_id)})

            return Response(
                {"response": "record_deleted"}, status=status.HTTP_202_ACCEPTED
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UserManage(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def get(self, request):
        mongo = Mongo()
        users_collection = mongo.connect("authentication_my_user")
        roles_collection = mongo.connect("roles")
        user_roles_collection = mongo.connect("user_has_roles")

        all_users = [
            normalize_user_document(user, context="UserManage.get")
            for user in users_collection.find(build_user_collection_query({"deleted_at": None}))
        ]

        users_active_json = []
        users_inactive_json = []

        for user in all_users:
            user_id = user.get("id")
            if user_id is None:
                logger.warning("Skipping user document without _id in UserManage.get: %s", user)
                continue

            roles = []
            roles_id = []
            lookup_ids = get_user_lookup_ids(user["raw"])
            results = list(user_roles_collection.find({"model_id": {"$in": lookup_ids}}))

            for item in results:
                role_data = roles_collection.find_one({"_id": item.get("role_id")})
                if not role_data:
                    logger.warning(
                        "Missing role document for user %s with role_id=%s",
                        user_id,
                        item.get("role_id"),
                    )
                    continue

                role_name = role_data.get("name", "Unknown")
                roles.append(role_name)
                roles_id.append(
                    {
                        "name": role_name,
                        "id": str(role_data.get("_id", "Unknown")),
                    }
                )

            payload = {
                "user": user.get("username", ""),
                "email": user.get("email", ""),
                "rol": roles,
                "_id": user_id,
            }

            if user.get("is_active", True):
                payload["rol_w_id"] = roles_id
                users_active_json.append(payload)
                continue

            deletable = True
            if user.get("object_id") is not None:
                deletable = not mongo.searchUserInCollections(user["object_id"])
            payload["deletable"] = deletable
            users_inactive_json.append(payload)

        roles = [
            {"name": role.get("name"), "id": str(role.get("_id"))}
            for role in roles_collection.find()
        ]
        roles_id = [{"name": role.get("name")} for role in roles]

        return Response(
            {
                "users_active": users_active_json,
                "users_inactive": users_inactive_json,
                "roles": roles,
                "roles_id": roles_id,
            },
            status=status.HTTP_200_OK,
        )


class SignupView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def post(self, request):

        # Extraer los datos del campo 'formData'
        form_data = request.data.get("formData", {})

        mongo = Mongo()
        users_collection = mongo.connect("authentication_my_user")
        counters_collection = mongo.connect(USER_COUNTER_COLLECTION)
        try:
            role_id = ObjectId(form_data.get("role", ""))
        except Exception:
            return Response(
                {"error": "El rol seleccionado no es válido"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if mongo.connect("roles").find_one({"_id": role_id}) is None:
            return Response(
                {"error": "El rol seleccionado no existe"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        legacy_counter = users_collection.find_one({"_id": LEGACY_USER_COUNTER_ID})
        if legacy_counter:
            logger.warning(
                "Migrating legacy user counter document out of authentication_my_user: %s",
                legacy_counter,
            )
            counters_collection.update_one(
                {"_id": USER_COUNTER_KEY},
                {"$max": {"sequence": int(legacy_counter.get("max_count_id", 0))}},
                upsert=True,
            )
            users_collection.delete_one({"_id": LEGACY_USER_COUNTER_ID})

        counter = counters_collection.find_one({"_id": USER_COUNTER_KEY})
        if counter is None:
            last_user = users_collection.find_one(
                build_user_collection_query({"id": {"$type": "number"}}),
                sort=[("id", -1)],
                projection={"id": 1},
            )
            initial_value = last_user.get("id", 0) if last_user else 0
            counters_collection.insert_one(
                {"_id": USER_COUNTER_KEY, "sequence": initial_value}
            )

        counter = counters_collection.find_one_and_update(
            {"_id": USER_COUNTER_KEY},
            {"$inc": {"sequence": 1}},
            return_document=ReturnDocument.AFTER,
        )
        new_value = counter["sequence"]

        formatted_data = {
            "username": form_data.get("NewName", ""),
            "password": form_data.get("NewPassword", ""),
            "email": form_data.get("NewEmail", ""),
            "id": new_value,
        }

        # Validar y guardar los datos con el serializer
        serializer = SignupSerializer(data=formatted_data)

        if serializer.is_valid():
            try:
                user = serializer.save()
                inserted_user = users_collection.find_one({"id": new_value})
                mongo.connect("user_has_roles").insert_one(
                    {"model_id": inserted_user["_id"], "role_id": role_id}
                )
            except Exception as e:
                print("NameError occurred. ", e)
                return Response(
                    {"error": str(e)}, status=status.HTTP_400_BAD_REQUEST
                )  # Responder la excepcion de que ya existe para actuar

            if user:
                return Response(
                    {"message": "new_user_added"},
                    status=status.HTTP_201_CREATED,
                )

        return Response(
            {"message": "No se pudo crear usuario", "usuario": request.data},
            status=status.HTTP_400_BAD_REQUEST,
        )  # Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CheckAccesToken(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def post(self, request):

        authorization_header = request.headers.get("Authorization")

        # print(f"Authorization Header: {authorization_header}")  # Añade este log
        username = request.user.username

        if authorization_header:
            # Dividir el encabezado Authorization para obtener el token de acceso
            parts = authorization_header.split()
            access_token = None
            if len(parts) == 2 and parts[0].lower() == "bearer":
                access_token = parts[1]
                # Ahora puedes usar access_token como desees

            if access_token is not None:
                decoded_token = jwt.decode(
                    access_token, options={"verify_signature": False}
                )  # No se verifica la firma aquí, solo decodifica
            expiration_time = decoded_token.get("exp", None)

            if expiration_time is not None:
                # Obtener el tiempo actual en formato UNIX timestamp
                current_time = time()

                # Calcular el tiempo restante antes de que el token expire
                time_left = expiration_time - current_time

                # print(user_permissions,'desde aca')
                return Response({"time_left": time_left, "user": str(username)})
        return Response({"error": "Can not obtain the user name"})


class SavePermissions:
    pass
