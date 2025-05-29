# Create your views here.
from math import e
from wsgiref.handlers import format_date_time
import jwt
#from django.contrib.auth.models import User
from django.contrib.auth import get_user_model

from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import authenticate
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from .mongo_queries import getPermissions
from time import time
from user_queries.driver_database.mongo import Mongo
User = get_user_model()

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):
        
        email = data.get("email")
        password = data.get("password")
        
        authenticated_user = authenticate(username=email, password=password)
        
        print("authenticated_user", authenticated_user)
        if authenticated_user:
            if authenticated_user.is_active:
                data["user"] = authenticated_user                
                return data
            else:
                raise serializers.ValidationError("La cuenta del usuario está desactivada.")
        else:
            raise serializers.ValidationError("No se pudo autenticar al usuario con las credenciales proporcionadas.")

class Permission:
    def get_permission(self, user):
        mongo = Mongo()
        collection = mongo.connect('user_has_roles')
        cursor = collection.aggregate(getPermissions(user))

        # Almacenar el resultado en una lista
        results = list(cursor)
        for item in results:
            
            permissions_info = item['permissions_info']
            overwrite_permissions_info = item['overwrite_permissions_info']
            for overwrite_perm in overwrite_permissions_info:
                # Verificar si el permiso ya existe
                for i, perm in enumerate(permissions_info):
                    if perm['id'] == overwrite_perm['id']:
                        permissions_info[i] = overwrite_perm  # Sobrescribir
                        break
                    else:
                        if overwrite_perm not in permissions_info:
                            permissions_info.append(overwrite_perm)  # Agregar si no existe
            
            names = [perm['name'] for perm in permissions_info]
            
            #names = ['ver_usuarios', 'ver_roles', 'ver_catalogos', 'ver_configuraciones']
            #print(names)
            return names
    

class signinView(APIView):
    authentication_classes = []  # Desactiva la autenticación
    permission_classes = [AllowAny]  # Permite a cualquiera acceder a esta vista

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        #print(request.data)
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            
            #print("user",user)
            refresh = RefreshToken.for_user(user)
            #print(user)
            permission = Permission()            
            user_permissions = permission.get_permission(user)
                        
            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user": str(user), 
                    "permissions": str(user_permissions),                    
                },
                status=status.HTTP_202_ACCEPTED,
                )
        else:
            # Si los datos de la solicitud no son válidos, devolver los errores de validación
            return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)
        
    def put(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response({"error": "Se requiere de un token"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            refresh_token = RefreshToken(refresh)
            user_id = refresh_token.payload['user_id']
            user = User.objects.get(id=user_id)
            access_token = str(refresh_token.access_token)            
            user = request.user                
            permission = Permission()            
            user_permissions = permission.get_permission(user)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"access": access_token, "user": user.username, "user_permissions": user_permissions}, status=status.HTTP_200_OK)
    
class SignupSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField()
    id = serializers.IntegerField()

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class InactiveUser(APIView):
    permission_classes = [IsAuthenticated]
    
    def patch(self, request):
        print("inactive api")
        try:
            userId= request.data.get("user_id")
            print(userId)
            user = get_object_or_404(User, id=userId)
            user.is_active = False
            user.save()
            return Response({"response":"record_changed"}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:            
            return Response({"error":str(e)}, status=status.HTTP_400_BAD_REQUEST)    
        
class ActivateUser(APIView):
    
    permission_classes = [IsAuthenticated]
    
    def patch(self, request):
        
        try:
            userId= request.data.get("user_id")
            print(userId)
            user = get_object_or_404(User, id=userId)
            user.is_active = True
            user.save()
            return Response({"response":"record_changed"}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:            
            return Response({"error":str(e)}, status=status.HTTP_400_BAD_REQUEST)    
    
        
        
class EditUser(APIView):
    permission_classes = [IsAuthenticated]
    
    def patch(self, request):
        try:
            
           
            data = request.data.get("formDataChange")
            userId= data.get("user_id")                        
            user = User.objects.get(id=userId)
            user.username = data.get("user")
            user.email = data.get("email")
            password = data.get("password")
            rol_name = data.get("rol")
            rol_id = data.get("rol_id")
            
            mongo = Mongo()
            
            collection_check = mongo.connect('user_has_roles')
            cursor = collection_check.find_one({'model_id': int(userId)})
            print(userId)
            if cursor.get("role_id") != rol_id:
                print("entro")   
                collectionRoles = mongo.connect('roles')
                cursor = collectionRoles.find_one({'id': int(rol_id) } )
                if cursor.get("name") == rol_name:
                    print("entro2")
                    collection = mongo.connect('user_has_roles')
                    cursor = collection.update_one(
                        {"model_id": int(userId)},
                        {"$set": {"role_id": int(rol_id)}}
                    )
                else:
                    return Response({"error":"El rol no coincide con el id"}, status=status.HTTP_400_BAD_REQUEST)
                            
            
            if password:
                user.set_password(password)
            user.save()
            return Response({"response":"user_updated"}, status=status.HTTP_202_ACCEPTED)
        
        except Exception as e:
            return Response({"error":str(e)}, status=status.HTTP_400_BAD_REQUEST)
            
class DeleteUser(APIView):
    permission_classes = [IsAuthenticated]
    
    def delete(self, request):
        try:
            userId= request.data.get("user_id")
            user = User.objects.get(id=userId)
            mongo = Mongo()
            collection = mongo.connect('deleted_auth_users')
            collection.insert_one(
                {
                    "username": user.username,
                    "email": user.email,
                    "id": user.id
                }
            )
            
            user.delete()
            return Response({"response":"record_deleted"}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"error":str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
class UserManage(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Obtén todos los usuarios
        all_users = User.objects.all()
        # Filtra los usuarios activos e inactivos
        
                
            
        users_active = [
            {'id': user.id, 'username': user.username, 'email': user.email}
            for user in all_users if user.is_active
        ]
        #print (users_active)
        users_inactive = [
            {'id': user.id, 'username': user.username, 'email': user.email}
            for user in all_users if not user.is_active
        ]
        #print("users_inactivesss",users_inactive)
        # Convertir usuarios a JSON
        users_active_json = []
        users_inactive_json = []
        mongo = Mongo()
        # Procesar usuarios activos
        for user in users_active:
            user_id = user.get("id")
            roles = []
            rolesId = []
            if user_id is not None:
                # Consulta en MongoDB
                collection = mongo.connect('user_has_roles')
                cursor = collection.find({'model_id': int(user_id)})
                results = list(cursor)
                
                for item in results:
                    collection = mongo.connect('roles')
                    role_data = collection.find_one({'id': int(item["role_id"])})
                    roles.append(role_data.get("name", "Unknown"))
                    rolesId.append({"name":role_data.get("name","unknown") ,"id":role_data.get("id", "Unknown")})
                # Agregar al JSON de usuarios activos
                users_active_json.append({
                    "user": user.get("username", ""),
                    "email": user.get("email", ""),
                    "rol": roles,
                    "rol_w_id": rolesId,
                    "_id": user_id
                })
                
        # Procesar usuarios inactivos
        for user in users_inactive:
            user_id = user.get("id")
            roles = []
            rolesId = []
            deletable = True
            if user_id is not None:
                # Consulta en MongoDB
                collection = mongo.connect('user_has_roles')
                cursor = collection.find({'model_id': int(user_id)})
                results = list(cursor)

                for item in results:
                    collection = mongo.connect('roles')
                    role_data = collection.find_one({'id': int(item["role_id"])})
                    if role_data:
                        roles.append(role_data.get("name", "Unknown"))
                       
                deletable = not mongo.searchUserInCollections(user_id)

            # Agregar al JSON de usuarios inactivos
            if user_id is not None:
                users_inactive_json.append({
                    "user": user.get("username", ""),
                    "email": user.get("email", ""),
                    "rol": roles,
                    "_id": user_id,
                    "deletable": deletable
                })

        roles = mongo.connect('roles')
        roles = list(roles.find())
        #aparte de el name del rol tambien obtener el id
        roles = [{"name": role.get("name"), "id": role.get("id")} for role in roles]
        roles_id = [{"name": role.get("name")} for role in roles]
        
        #print("users_inactive",users_inactive_json)
        # Responder con los datos procesados
        return Response(
            {"users_active": users_active_json, "users_inactive": users_inactive_json , "roles": roles,"roles_id": roles_id},
            status=status.HTTP_200_OK
        )


class SignupView(APIView):
    permission_classes = [IsAuthenticated]
  
        
    def post(self, request):
        print("si ocurre");
        #print(request.data)
        # Extraer los datos del campo 'formData'
        form_data = request.data.get('formData', {})
        print("form_data",form_data)
        # Mapear los campos a los requeridos por el serializer
        mongo = Mongo()
        collection = mongo.connect("auth_user")
        #en auth_user hay una objeto que tiene el nombre max_count_id, filtrarlo por nombre y luego aumentarle 1        
        cursor = collection.find_one({"max_count_id": {"$exists": True}})
        print(cursor)
        if cursor:
            # Extraer el valor actual de "max_count_id"
            current_value = cursor.get("max_count_id", 0)  # Si el campo no existe, toma 0 como valor por defecto
            
            # Sumar 1 al valor
            new_value = current_value + 1
            
        
        formatted_data = {
            'username': form_data.get('NewName', ''),  # Convertir 'name' a 'username'
            'password': form_data.get('newPassword', ''),
            'email': form_data.get('NewEmail', ''),
            "id": new_value
        }
        
        print("formated_data",formatted_data)
        # Validar y guardar los datos con el serializer
        serializer = SignupSerializer(data=formatted_data)

        if serializer.is_valid():
            try:
                user = serializer.save()
                collection.update_one(
                    {"_id": cursor["_id"]},  # Condición para encontrar el documento por su ID
                    {"$set": {"max_count_id": new_value}}  # Actualización del campo
                )
                
                collection = mongo.connect("user_has_roles")
                # Crear un documento en la colección user_has_roles
                collection.insert_one(
                    {
                        "model_id": new_value,
                        "role_id": int(form_data.get("role", 0))
                    }
                )
            except Exception as e:
                print("NameError occurred. ",e)
                return Response(
                    {"Error", str(e)}
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
    authentication_classes = [JWTAuthentication]
    def post (self, request):
        
        authorization_header = request.headers.get("Authorization")
        #print(f"Authorization Header: {authorization_header}")  # Añade este log
        username = request.user.username
        print(f"Authenticated User: {username}")  # Añade este log
        if authorization_header:
            # Dividir el encabezado Authorization para obtener el token de acceso
            parts = authorization_header.split()
            access_token = None
            if len(parts) == 2 and parts[0].lower() == "bearer":
                access_token = parts[1]
                # Ahora puedes usar access_token como desees
            
            if access_token is not None:
                decoded_token = jwt.decode(access_token, options={"verify_signature": False})  # No se verifica la firma aquí, solo decodifica
            expiration_time = decoded_token.get('exp', None)

            if expiration_time is not None:
                # Obtener el tiempo actual en formato UNIX timestamp
                current_time = time()

                # Calcular el tiempo restante antes de que el token expire
                time_left = expiration_time - current_time               
                
                #print(user_permissions,'desde aca')                
                return Response({"time_left":time_left, "user":str(username)})
        return Response({"error":"Can not obtain the user name"})
    

class SavePermissions():        
    pass


