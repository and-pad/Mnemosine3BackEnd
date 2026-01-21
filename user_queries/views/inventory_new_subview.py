
#import json
#from bson import ObjectId
from user_queries.views.common.utils import get_collection_json, get_catalog_elements

"""
def get_collection_json(self, mongo, collection_name, query=None, sort_field=None):
        #Obtiene documentos de una colección y los convierte a JSON.
        collection = mongo.connect(collection_name)
        cursor = collection.find(query or {})
        if sort_field:
            cursor = cursor.sort(sort_field, 1)
        return json.loads(json.dumps(list(cursor), default=str))

def get_catalog_elements(self, mongo, code):
    #Obtiene los elementos de un catálogo dado su código.
    catalog = mongo.connect("catalogs").find_one({"code": code})
    if catalog:
        return get_collection_json(
            mongo, "catalog_elements", {"catalog_id": ObjectId(catalog["_id"])}
        )
    return []
"""

def process_get(mongo):
    #data_get= list(mongo.connect("genders").find())
    response_data = {
        "genders": get_collection_json(
            mongo, "genders", {"deleted_at": None}, "title"
        ),
        "subgenders": get_collection_json(
            mongo, "subgenders", {"deleted_at": None}, "title"
        ),
        "type_object": get_catalog_elements(mongo, "object_type"),
        "dominant_material": get_catalog_elements(
            mongo, "dominant_material"
        ), 

    }


    return response_data
