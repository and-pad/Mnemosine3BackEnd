
import os
import random
import string
import shutil
from bson import ObjectId
from user_queries.driver_database import mongo
from user_queries.driver_database.mongo import Mongo
from ..tools import AuditManager
from django.conf import settings
from PIL import Image
from user_queries.shemas.photograph_shema import PhotographSchema


def generate_random_file_name(original_filename, length=40):
    _, extension = os.path.splitext(original_filename)
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choices(alphabet, k=length)) + extension


def get_research_id(_id):
    """Obtiene el ID de investigación a partir del ID de pieza."""
    mongo = Mongo()
    research = mongo.connect("researchs").find_one(
        {"piece_id": ObjectId(_id), "deleted_at": None}, {"_id": 1}
    )
    return str(research["_id"]) if research else None

def get_module_id(module_name, mongo = Mongo()):
        """Obtiene el ID de un módulo por su nombre."""
        module = mongo.connect("modules").find_one(
            {"name": module_name, "deleted_at": None}, {"_id": 1}
        )
        return module["_id"] if module else None
    
def format_new_pic( pic,user_id, moduleId, _id):
        try:
            new_picture = {
                        "photographer": pic.get("photographer") or None,
                        "photographed_at": pic.get("photographed_at") or None, 
                        "description": pic.get("description") or None,
                        "file_name": pic.get("file_name"), 
                        "module_id": ObjectId(moduleId),
                        "piece_id": ObjectId(_id),
                        "size": pic.get("size"),
                        "mime_type": pic.get("mime_type"),
                    }
        except Exception as e:
            print("Error al formatear nueva foto faltan datos:", e)
            return None
            
                # Con AuditManager le agregamos info de timestamps y auditoria de usuario
        return AuditManager().add_photoInfo(new_picture, user_id)
    
    

def process_thumbnail(pic):
    try:
        origin = os.path.join(settings.PHOTO_RESEARCH_PATH, pic["file_name"])
        # Creamos el thumbnail en la carpeta de thumbnails
        destination = os.path.join(
            settings.THUMBNAILS_RESEARCH_PATH, pic["file_name"]
        )
        # Creamos el objeto Image para abrir la imagen y cambiarle el tamaño
        img = Image.open(origin)
        # Tamaño del thumbnail
        width_thumbnail = 100
        height_thumbnail = int(img.height * (width_thumbnail / img.width))
        # Creamos el thumbnail cambiandole el tamaño ajustado a la proporcion anterior
        img_thumbnail = img.resize((width_thumbnail, height_thumbnail))
        # Guardamos el thumbnail
        img_thumbnail.save(destination)
    except Exception as e:
        print("No se pudo crear el thumbnail Error: ", e)
    

def add_delete_to_actual_photo_file_name(file_name):
        origin = os.path.join(settings.PHOTO_RESEARCH_PATH, file_name)
        destination = os.path.join(settings.PHOTO_RESEARCH_PATH, f"deleted_{file_name}")
                    
        origin_thumbnail = os.path.join(settings.THUMBNAILS_RESEARCH_PATH, file_name)
        destination_thumbnail = os.path.join(settings.THUMBNAILS_RESEARCH_PATH, f"deleted_{file_name}")
        
        # Esto puede salir mal por falta de permisos, pero le hacemos una comprobacion de error y seguimos
        try:
            shutil.move(origin, destination)
            shutil.move(origin_thumbnail, destination_thumbnail)
        except Exception as e:
            print("No se pudo mover el thumbnail Error: ", e)
def add_delete_to_actual_document_file_name(document_id):
    file_name = Mongo().connect("documents").find_one({"_id": ObjectId(document_id)}).get("file_name")        
    origin = os.path.join(settings.DOCUMENT_RESEARCH_PATH, file_name)
    destination = os.path.join(settings.DOCUMENT_RESEARCH_PATH, f"deleted_{file_name}")
    try:
        shutil.move(origin, destination)
    except Exception as e:
        print("No se pudo mover el documento Error: ", e)
            
def store_pic_changes(pic, user_id):

    return Mongo().connect("photographs").update_one(
        {"_id": ObjectId(pic["_id"])},
        {
            "$set": PhotographSchema(**AuditManager().add_updateInfo(_format_pic_data_to_update(pic), user_id)).model_dump(exclude_none=True),
        },
    )
    
def _format_pic_data_to_update(pic):
    return  {
        "file_name": pic.get("file_name") or None,
        "size": pic.get("size") or None,
        "mime_type": pic.get("mime_type") or None,                    
    }                   

def _map_field_name(key: str, field_map: dict) -> str:
    """Mapea el nombre de un campo al nombre esperado en la base de datos."""
    return field_map.get(key, key)

def _convert_list_to_object_ids(key: str, items: list) -> list:
    """Convierte una lista de dicts con _id a una lista de ObjectId."""
    ids = []
    for item in items:
        if isinstance(item, dict) and "_id" in item:
            try:
                ids.append(ObjectId(item["_id"]))
            except Exception as e:
                print(f"⚠️ Error al convertir ID en {key}: {item['_id']} ({e})")
    return ids

def _convert_dict_to_object_id(key: str, value: dict):
    """Convierte un dict con _id a un ObjectId."""
    try:
        return ObjectId(value["_id"])
    except Exception as e:
        print(f"⚠️ Error al convertir ID en {key}: {value['_id']} ({e})")
        return None

def _process_field(key: str, value, field_map: dict):
    """
    Procesa un campo y devuelve (clave_mapeada, valor_convertido) o None si no aplica.
    """
    if not isinstance(value, dict) or "newValue" not in value:
        return None

    new_value = value["newValue"]
    mapped_key = _map_field_name(key, field_map)

    if isinstance(new_value, list):
        return mapped_key, _convert_list_to_object_ids(key, new_value)

    elif isinstance(new_value, dict) and "_id" in new_value:
        return mapped_key, _convert_dict_to_object_id(key, new_value)

    elif isinstance(new_value, (str, type(None))):
        return mapped_key, new_value

    else:
        print(f"⚠️ Formato no reconocido para '{key}': {new_value}")
        return None

# --- Función principal ---

def format_research_data(changes, inventory_fields ):
    """
    Formatea los cambios de investigación, mapeando campos y convirtiendo IDs a ObjectId.
    """
    field_map = {
        "authors": "author_ids",
        "period": "period_id",
        "place_of_creation": "place_of_creation_id",
        "involved_creation": "involved_creation_ids",
    }

    researchData = {}

    for key, value in changes.items():
        if key in inventory_fields:
            continue
        if result:= _process_field(key, value, field_map):
            mapped_key, converted_value = result
            researchData[mapped_key] = converted_value

    return researchData