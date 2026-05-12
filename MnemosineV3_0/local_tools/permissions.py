import json
import sys
import os
import argparse
from bson import ObjectId
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from user_queries.driver_database.mongo import Mongo




class importPermissions:
    
    def chargeData(self):
        ruta_archivo = os.path.join(os.path.dirname(__file__), 'roles_.json')
        with open(ruta_archivo, 'r') as archivo:            
            datos = json.load(archivo)
        
        self.inserttoMongo(datos,'roles')

        
        for rol in datos['roles']:
            print(rol)
            
        #print(datos['roles'])
    
    def inserttoMongo(self,datos, name):
        
        mongo = Mongo()
        mongo.checkAndDropIfExistCollection(name)            
        collection = mongo.connect(name)
        collection.insert_many(datos[name])
        

    def chargeRole_has_per(self):
        ruta_archivo = os.path.join(os.path.dirname(__file__), 'role_has_permissions.json')
        with open(ruta_archivo, 'r') as archivo:            
            datos = json.load(archivo)
        
        self.inserttoMongo(datos, 'role_has_permissions')
        
        
    def chargeUser_has_permission(self):
        ruta_archivo = os.path.join(os.path.dirname(__file__), 'user_has_permission.json')
        with open(ruta_archivo, 'r') as archivo:            
            datos = json.load(archivo)
        
        mongo = Mongo()
        mongo.checkAndDropIfExistCollection("user_has_permissions")            
        collection = mongo.connect('user_has_permissions')
        collection.insert_many(datos['model_has_permissions'])
        
    def chargePermissions(self):
        ruta_archivo = os.path.join(os.path.dirname(__file__), 'permissions.json')
        
        with open(ruta_archivo, 'r') as archivo:            
            datos = json.load(archivo)
            
        self.inserttoMongo(datos, 'permissions')
        print("te la mamaste morro permissions is added !")
    
    def chargeUser_has_roles(self):
        ruta_archivo = os.path.join(os.path.dirname(__file__), 'user_has_roles.json')
        with open(ruta_archivo, 'r') as archivo:            
            datos = json.load(archivo)
        
        mongo = Mongo()
        mongo.checkAndDropIfExistCollection("user_has_roles")            
        collection = mongo.connect('user_has_roles')
        collection.insert_many(datos['model_has_roles'])
        




class Transform_id:

    def role_has_permissions(self):
        mongo = Mongo()
        collection = mongo.connect('roles')
        collection_rhp = mongo.connect('role_has_permissions')
        cursor_rol = collection.find()
        for rol in cursor_rol:
            id_rol = rol['id']
            print(f"Migrando role_id {id_rol} → {rol['_id']}")           
            result = collection_rhp.update_many(
                {"role_id": id_rol},
                {"$set": {
                        "role_id": rol['_id']
                    }
                }
            )
            print(result.modified_count)
    
    def role_has_permissions_permissions(self):
        mongo = Mongo()
        collection_per = mongo.connect('permissions')
        collection_rhp = mongo.connect('role_has_permissions')
        cursor_per = collection_per.find()
        for per in cursor_per:
            id_per = per['id']
            print(f"Migrando permission_id {id_per} → {per['_id']}")
            result = collection_rhp.update_many(
                {"permission_id": id_per},
                {"$set": {
                        "permission_id": per['_id']
                    }
                }
            )
            print(result.modified_count)

    def user_has_roles(self):        
        mongo = Mongo()
        collection_roles = mongo.connect('roles')
        collection_uhr = mongo.connect('user_has_roles')
        collection_users = mongo.connect('authentication_my_user')

        cursor_rol = collection_roles.find()
        for rol in cursor_rol:
            id_rol = rol['id']
            print(f"Migrando role_id {id_rol} → {rol['_id']}")           
            result = collection_uhr.update_many(
                {"role_id": id_rol},
                {"$set": {
                        "role_id": rol['_id']
                    }
                }
            )
            print(result.modified_count)
        
        cursor_users = collection_users.find()
        for user in cursor_users:
            id_user = user['id']
            print(f"Migrando user_id {id_user} → {user['_id']}")           
            result = collection_uhr.update_many(
                {"model_id": id_user},
                {"$set": {
                        "model_id": user['_id']
                    }
                }
            )
            print(result.modified_count)
    
    def user_has_permissions(self):
        mongo = Mongo()
        collection_per = mongo.connect('permissions')
        collection_uhp = mongo.connect('user_has_permissions')
        collection_users = mongo.connect('authentication_my_user')

        cursor_per = collection_per.find()
        for per in cursor_per:
            id_per = per['id']
            print(f"Migrando permission_id {id_per} → {per['_id']}")
            result = collection_uhp.update_many(
                {"permission_id": id_per},
                {"$set": {
                        "permission_id": per['_id']
                    }
                }
            )
            print(result.modified_count)
        cursor_users = collection_users.find()
        for user in cursor_users:
            id_user = user['id']
            print(f"Migrando user_id {id_user} → {user['_id']}")           
            result = collection_uhp.update_many(
                {"model_id": id_user},
                {"$set": {
                        "model_id": user['_id']
                    }
                }
            )
            print(result.modified_count)
        
        
if __name__ == "__main__":
    # Configuración de argparse para capturar múltiples opciones
    parser = argparse.ArgumentParser(description='Selecciona una o varias operaciones a ejecutar: op1, op2, etc.')
    parser.add_argument('opciones', type=str, nargs='+', help='Opciones a ejecutar (op1, op2, op3, etc.)')

    # Capturar los argumentos
    args = parser.parse_args()

    # Crear una instancia de la clase
    permission = importPermissions()

    # Diccionario que mapea la opción a la función correspondiente
    opciones = {
        'op1': permission.chargeData,
        'op2': permission.chargeRole_has_per,
        'op3': permission.chargeUser_has_permission,
        'op4': permission.chargePermissions,
        'op5': permission.chargeUser_has_roles,
        'Transform_id': Transform_id().role_has_permissions,
        'Transform_id_per': Transform_id().role_has_permissions_permissions,
        'Transform_id_user': Transform_id().user_has_roles,
        'Transform_id_user_per': Transform_id().user_has_permissions
    }

    # Ejecutar las funciones correspondientes
    for opcion in args.opciones:
        func = opciones.get(opcion)
        if func:
            func()
        else:
            print(f"Opción {opcion} no válida. Usa op1, op2, op3, op4 o op5, Transform_id.")