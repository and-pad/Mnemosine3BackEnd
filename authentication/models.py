from unittest import result
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

from user_queries.driver_database.mongo import Mongo

class MyUserManager(BaseUserManager):
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not email:
            raise ValueError("Se requiere un email.")
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(username, email, password, **extra_fields)



class my_user(AbstractUser):
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = MyUserManager()

    def __str__(self):
        return self.username





class Changes:
    
    def __change_deleted_at_for_inactive_users(self):
        mongo = Mongo()
        collection = mongo.connect("authentication_my_user")
        
        # Buscar usuarios que tienen una fecha en deleted_at (no es None)
        cursor = collection.find({"deleted_at": {"$ne": None}})

        for doc in cursor:
            result =collection.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "is_active": False,
                        "deleted_at": None
                    }
                }
            )
            print(f"Updated document with _id: {doc['_id']}, modified count: {result.modified_count}")
        


if __name__ == "__main__":
    changes = Changes()
    changes.__change_deleted_at_for_inactive_users()