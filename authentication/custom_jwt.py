import jwt
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
#from time import time
from bson import ObjectId

from user_queries.driver_database.mongo import Mongo  # tu clase Mongo nativa

SECRET = "Ax100_2022_xLk8optaeqna9d5WdAfCeeGdLk84YgDe"

class CustomJWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth = request.headers.get("Authorization", None)
        if not auth:
            return None

        parts = auth.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise AuthenticationFailed("Token malformado")

        token = parts[1]

        try:
            payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed("Token expirado")
        except Exception:
            raise AuthenticationFailed("Token inválido")

        # Ya NO se usa Django ORM aquí
        user_id = payload.get("user_id")
        if not user_id:
            raise AuthenticationFailed("Token sin user_id")

        # cargar usuario directo de Mongo nativo
        mongo = Mongo()
        users = mongo.connect("authentication_my_user")
        user = users.find_one({"_id": ObjectId(user_id)})
       
        if not user:
            raise AuthenticationFailed("Usuario no encontrado")

        # lo enviamos como objeto simple
        request.user = SimpleUser(user)

        return (request.user, None)


class SimpleUser:
    def __init__(self, data):
        self.id = str(data["_id"])
        self.username = data.get("username")
        self.email = data.get("email")
        self.permissions = data.get("permissions", [])

    @property
    def is_authenticated(self):
        return True
