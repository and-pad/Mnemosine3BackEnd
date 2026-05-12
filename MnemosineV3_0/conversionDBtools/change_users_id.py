
from bson import ObjectId
import os
import sys
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from user_queries.driver_database.mongo import Mongo



def change_users_id():
    mongo = Mongo()
    #Aqui hay que ir cambiando de coleccion en coleccion
    cur_pieces = mongo.connect("research_changes_history")
    cur_users = mongo.connect("authentication_my_user")

    for piece in cur_pieces.find():
        # Inicializamos como None
        created_by_id = updated_by_id = deleted_by_id = None

        # Solo actualizamos si no es ObjectId ya
        if piece.get("created_by") and not isinstance(piece["created_by"], ObjectId):
            user = cur_users.find_one({"id": piece["created_by"]})
            if user:
                created_by_id = user["_id"]

        if piece.get("updated_by") and not isinstance(piece["updated_by"], ObjectId):
            user = cur_users.find_one({"id": piece["updated_by"]})
            if user:
                updated_by_id = user["_id"]

        if piece.get("deleted_by") and not isinstance(piece["deleted_by"], ObjectId):
            user = cur_users.find_one({"id": piece["deleted_by"]})
            if user:
                deleted_by_id = user["_id"]

        # Protegemos el print por si no hay photographs_id
        pid = piece.get("_id", piece["_id"])
        print(f"Updating piece ID: {pid}")
        print(f"  created_by: {piece.get('created_by')} -> {created_by_id}")
        print(f"  updated_by: {piece.get('updated_by')} -> {updated_by_id}")
        print(f"  deleted_by: {piece.get('deleted_by')} -> {deleted_by_id}")

        # Solo hacemos update si hay algo que cambiar
        update_data = {}
        if created_by_id: update_data["created_by"] = created_by_id
        if updated_by_id: update_data["updated_by"] = updated_by_id
        if deleted_by_id: update_data["deleted_by"] = deleted_by_id

        if update_data:
            cur_pieces.update_one({"_id": piece["_id"]}, {"$set": update_data})


if __name__ == "__main__":    
    change_users_id()