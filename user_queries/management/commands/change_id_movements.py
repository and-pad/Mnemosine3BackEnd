
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from user_queries.driver_database.mongo import Mongo



def change_id_movements():

    mongo = Mongo()
    movements = mongo.connect("movements").find({})
    #users = mongo.connect("authentication_my_user").find({})

    for movement in movements:
        movement_authorized_by = movement.get("authorized_by_movements")
        if isinstance(movement_authorized_by, int):
            user = mongo.connect("authentication_my_user").find_one({"id": movement_authorized_by})
            print("user", user["username"])
            user_id = user["_id"]
            mongo.connect("movements").update_one(
                {"_id": movement["_id"]},
                {"$set": {"authorized_by_movements": user_id}}
            )
            print(f"Updated movement {movement['_id']} authorized_by_movements to {user_id}")
        else:
            print(f"No update needed for movement {movement['_id']}")
    print("Completed updating movements.")


if __name__ == "__main__":
    change_id_movements()

