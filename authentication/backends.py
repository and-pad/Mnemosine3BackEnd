from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import check_password
from authentication.models import MyUser
from user_queries.driver_database.mongo import Mongo
from bson import ObjectId

class MongoAuthBackend(BaseBackend):

    def authenticate(self, request, email=None, username=None, password=None, **kwargs):
        # Django manda "username", no "email"
        
        email = email or username
        
        if not email or not password:
            print("No email or password provided")
            return None

        mongo = Mongo()
        coll = mongo.collection("authentication_my_user")

        # AQUÍ buscas por email en Mongo
        user_data = coll.find_one({"email": email, "deleted_at": None})
        
        if not user_data:
            return None

        user = MyUser(
            id=str(user_data["_id"]),
            email=user_data["email"],
            username=user_data.get("username", ""),
            first_name=user_data.get("first_name", ""),
            last_name=user_data.get("last_name", ""),
            is_staff=user_data.get("is_staff", False),
            is_superuser=user_data.get("is_superuser", False),
            is_active=user_data.get("is_active", True),
        )
        user.password = user_data["password"]        

        if check_password(password, user.password):
            return user

        return None

    def get_user(self, user_id):
        mongo = Mongo()
        coll = mongo.collection("users")
        data = coll.find_one({"_id": ObjectId(user_id)})

        if not data:
            return None

        user = MyUser(
            id=str(data["_id"]),
            email=data["email"],
            username=data.get("username", ""),
        )
        user.password = data["password"]
        return user