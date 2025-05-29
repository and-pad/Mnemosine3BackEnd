import os
import sys
from unittest import result
import django
import psycopg2

# Configura el entorno de Django
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(PROJECT_ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MnemosineV3_0.settings')
django.setup()

from user_queries.driver_database.mongo import Mongo

def add_timestamps_user():
    conn = psycopg2.connect(
        dbname="mnemosine",
        user="andres",
        password="123456",
        host="localhost",
        port="5432"
    )

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users ")

    colnames = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    
    users_info = []
    for row in rows:
        # row es una tupla; zip con colnames para formar dict
        row_dict = dict(zip(colnames, row))
        users_info.append(row_dict)
    
    #print("users_info:", users_info)

    mongo = Mongo()
    
    for user in users_info:
        result = mongo.connect("auth_user").update_one({"id": user["id"] }, {"$set": {"deleted_at": user["deleted_at"]}})
        print("user", user["id"])
        print("deleted_at", user["deleted_at"])
        print("modified_count", dict(result.raw_result))
    
    # Aquí puedes insertar o actualizar los datos en MongoDB si quieres

    cursor.close()
    conn.close()

#if __name__ == "__main__":
    #add_timestamps_user()
    
class Changes:
    
    def _change_deleted_at_for_inactive_users(self):
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
    #from tu_modulo_mongo import Mongo  # Ajusta al nombre correcto de tu archivo
    import argparse

    parser = argparse.ArgumentParser(description="Herramienta para actualizar usuarios.")
    parser.add_argument(
        "accion",
        choices=["changes", "timestamps"],
        help="Acción a ejecutar: 'activar' cambia usuarios eliminados a inactivos, 'saludo' imprime un saludo."
    )

    args = parser.parse_args()
    cleaner = Changes()

    if args.accion == "changes":
        print("Ejecutando cambios...")
        cleaner._change_deleted_at_for_inactive_users()
    elif args.accion == "timestamps":
        add_timestamps_user()
        
        
        
        
