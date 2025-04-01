from django import db
import pymongo

class Mongo: #En estas entradas del contsructor puedes poner tu usuario y password de desarrollo :)
    def __init__(self, db_name = "Mnemosine", user_name = "usuario1", password = "123456"):
        self.db_name = db_name
        self.user = user_name
        self.password = password
        self.client = pymongo.MongoClient(f"mongodb://{self.user}:{self.password}@localhost:27017/")
        
        
    def connect(self, dBcollection):        
        db = self.client[self.db_name]
        collection = db[dBcollection]
        return collection    
 
    def checkAndDropIfExistCollection(self, collection_name):                
        db = self.client[self.db_name]
        if collection_name in db.list_collection_names():
            db[collection_name].drop()
            return True
        return False
            
    def checkIfExistCollection(self, collection_name):                
        db = self.client[self.db_name]
        if collection_name in db.list_collection_names():
            return True
        return False

    # Función para buscar en todas las colecciones
    def searchUserInCollections(self, user_id):
        fields = ['created_by', 'updated_by', 'deleted_by']
        db = self.client[self.db_name]

        # Iterar sobre colecciones
        for collection_name in db.list_collection_names():
            collection = db[collection_name]
            # Construimos el filtro para los campos
            query = {"$or": [{field: user_id} for field in fields]}
            # Buscar el primer documento que coincida
            document = collection.find_one(query)
            if document:
                # Retornar el nombre de la colección donde se encontró la coincidencia
                return {"collection": collection_name, "document": document}
        
        # Si no hay coincidencias, retornamos None o un valor indicativo
        return None    
        
        

        