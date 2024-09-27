import pymongo

class Mongo: #En estas entradas del contsructor puedes poner tu usuario y password de desarrollo :)
    def __init__(self, db_name = "pymnemosine", user_name = "usuario1", password = "123456"):
        self.db_name = db_name
        self.user = user_name
        self.password = password
        
    def connect(self, dBcollection):                        
        client = pymongo.MongoClient(f"mongodb://{self.user}:{self.password}@localhost:27017/")
        db = client[self.db_name]
        collection = db[dBcollection]
        return collection    
 
    def checkAndDropIfExistCollection(self, collection_name):        
        client = pymongo.MongoClient(f"mongodb://{self.user}:{self.password}@localhost:27017/")
        db = client[self.db_name]
        if collection_name in db.list_collection_names():
            db[collection_name].drop()
        
        
            
        
        
               
        
        
          
        