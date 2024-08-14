

# Create your views here.

import jwt
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.authentication import JWTAuthentication


from time import time



class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):
        
        UserModel = get_user_model()          
        users = UserModel.objects.filter(email=data.get("email"))
        
        if not users:
            raise serializers.ValidationError(
                "No se encontró ningún usuario con este correo electrónico."
            )
        
        for user in users:
            username = user.get_username()
            password = data.get("password")
            print(username)
            
            if username and password:
                authenticated_user = authenticate(username=username, password=password)
                if authenticated_user:
                    if authenticated_user.is_active:
                        data["user"] = authenticated_user
                        return data  # Salir del bucle y retornar los datos validados
                    else:
                        raise serializers.ValidationError(
                            "La cuenta del usuario está desactivada."
                        )
                else:
                    # Si la autenticación falla, continuar con el siguiente usuario
                    continue

        raise serializers.ValidationError(
            "No se pudo autenticar ningún usuario con las credenciales proporcionadas."
        )
        return data


class signinView(APIView):
    authentication_classes = []  # Desactiva la autenticación
    permission_classes = [AllowAny]  # Permite a cualquiera acceder a esta vista

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            refresh = RefreshToken.for_user(user)
            print(user)
            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user": str(user), 
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
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"access": access_token, "user": user.username}, status=status.HTTP_200_OK)
        


class SignupSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField()

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class SignupView(APIView):
    authentication_classes = []  # Desactiva la autenticación
    permission_classes = [AllowAny]  # Permite a cualquiera acceder a esta vista

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.save()
            except Exception as e:
                print("NameError occurred.")
                return Response(
                    {"Error", str(e)}
                )  # Responder la excepcion de que ya existe para actuar

            if user:
                return Response(
                    {"message": "Usuario creado exitosamente"},
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
                return Response({"time_left":time_left, "user":str(username)})
        return Response({"error":"Can not obtain the time"})