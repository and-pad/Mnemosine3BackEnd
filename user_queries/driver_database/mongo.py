import pymongo

class Mongo:

    def connect(self, dBcoleccion):
        db_name = "pymnemosine"
        coleccion = dBcoleccion
        usuario = "usuario1"
        contraseña = "123456"
        cliente = pymongo.MongoClient(
            "mongodb://{}:{}@localhost:27017/".format(usuario, contraseña)
        )
        db = cliente[db_name]
        coleccion = db[coleccion]
        return coleccion
    
    """
    def execute(self, collection=None, data=None):
        cursor = collection.find().limit(10)
        return cursor
    """
        