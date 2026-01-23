
from hmac import new
import json
from math import pi
import re
from unittest import result

from bson import ObjectId
from bson import ObjectId
from user_queries.shemas.piece_shema import PieceSchema
from user_queries.views.common.utils import get_collection_json, get_catalog_elements
from user_queries.views.tools import AuditManager
from user_queries.views.common.utils import generate_random_file_name
from django.conf import settings
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


def process_post(request, mongo):
    user_id = request.user.id

    changes_raw = request.data.get("changes")
    if not changes_raw:
        return {}
    
    pics = json.loads(request.data.get("PicsNew",{}))
    pics_info = None
    if pics:           
        pics_info = _process_pics( pics, request)


    docs = json.loads(request.data.get("DocumentsNew",{}))    
    docs_info = None
    if docs:           
        docs_info = _process_docs(docs, request)
    print("changes_raw:", changes_raw)
    changes = json.loads(changes_raw)

    inventory_fields = {}
    for field, payload in changes.items():
        inventory_fields[field] = payload.get("newValue")
    new_piece = {"new_piece":inventory_fields, **pics_info, **docs_info}
    audit = AuditManager()
    new_piece = audit.add_timestampsInfo(new_piece, ObjectId(user_id))
    
    with mongo.start_session() as session:
        try:
            with session.start_transaction():
                result =mongo.connect("inventory_change_approvals").insert_one(new_piece, session=session)                
        except Exception as e:
            print(f"Error al guardar cambios en la base de datos: {e}")
            raise e
    
    return result.inserted_id

def _process_pics( pics,  request):    

    pics_info = {}
    for index, pic in enumerate(pics):
        print("Processing pic:", pic)
        if file := request.FILES.get(f"files[new_img_{index}]"):

            filename = generate_random_file_name(file.name)

            pics_info.setdefault("new_pics", []).append(                
             {
                        "photographer": pic["photographer"],
                        "photographed_at": pic["photographed_at"],
                        "description": pic["description"],
                        "file_name": filename,
                        "size": pic["size"],
                        "mime_type": pic["mime_type"],
                    }
                )
            print(f"Saving temporary file '{filename}'")
            print(pics_info,"test2")
            try:
                _save_temporary_files(file, filename)
            except Exception as e:
                print(f"⚠️ Error saving temporary file '{filename}': {e}")
                raise e
    print("pics_info so far:", pics_info)
    return pics_info
    
def _process_docs(docs, request):    
    docs_info  = {}
    for index, doc in enumerate(docs):
        if file := request.FILES.get(f"files[new_doc_{index}]"):
            filename = generate_random_file_name(file.name)
            docs_info.setdefault("new_docs", []).append (
                {
                        "name": doc["name"],                        
                        "file_name": filename,
                        "size": doc["size"],
                        "mime_type": doc["mime_type"],
                    }            
            )
            try:
                _save_temporary_files(file, filename)                
            except Exception as e:
                print(f"⚠️ Error saving temporary document '{filename}': {e}")
                raise e
    return docs_info

        
            
            

def _save_temporary_files(file, filename):
    file_path = f"{settings.TEMPORARY_UPLOAD_DIRECTORY}{filename}"
    with open(file_path, "wb") as f:
        for chunk in file.chunks():
            f.write(chunk)
            
            
