#from django.contrib.auth.models import AbstractUser, BaseUserManager
#from django.db import models

from user_queries.driver_database.mongo import Mongo

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from bson import ObjectId
from datetime import datetime

# Este manager NO usa ORM, solo crea el objeto en RAM.
class MyUserManagerMongo(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Se requiere un email.")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)

        # Genera un ObjectId como id interno para Django
        if not user.id:
            user.id = str(ObjectId())
        #Aqui esta mal porque aun usamos el save y es de ORM, hace falta implementar el guardado en Mongo
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class MyUser(AbstractBaseUser, PermissionsMixin):
    """
    Modelo de usuario desconectado del ORM para DB,
    solo lo usamos en RAM para hash y auth.
    """
    id = models.CharField(primary_key=True, max_length=24, editable=False)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)    
    # Campos clásicos
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=datetime.now)
    deleted_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = MyUserManagerMongo()

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        # Evita que Django interfiera con DB (Mongo se maneja a mano)
        return super().save(*args, **kwargs)



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