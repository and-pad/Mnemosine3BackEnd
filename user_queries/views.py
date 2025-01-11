# imports
import json
import html
import time
import random
import string

import pytz
from bson import ObjectId
from bson.decimal128 import Decimal128
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .driver_database.mongo import Mongo
from .mongo_queries import *  # PIECES_ALL, PIECE_DETAIL
from django.conf import settings
from django.conf.urls.static import static
from docxtpl import DocxTemplate, InlineImage
from django.http import HttpResponse
from io import BytesIO
from datetime import datetime
from docx.shared import Mm
#from rest_framework_simplejwt.authentication import JWTAuthentication

from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from authentication.mongo_queries import getPermissions
from authentication.views import Permission

# from bson.json_util import dumps


class UserQueryAll(APIView): 
    permission_classes = [IsAuthenticated]
    dbCollection = "pieces"
    dbCollectionPics = "photographs"

    def get(self, request): 
        mongo = Mongo()        
        start = time.time()                
        
        search_collection = mongo.connect('pieces_search')        
        print("verifica")
        if not mongo.checkIfExistCollection('pieces_search'):
            print("no existe")           
        
            collection = mongo.connect(self.dbCollection)#conectacon la base de datos y una coleccion en especifico y regresa el conector para ejecutar instrucciones 
            cursor = collection.aggregate(PIECES_ALL)#la instruccion viene de mongo_queries  
            for document in cursor:
                search_collection.insert_one(document)  
        
            
        
                          
        cursor = search_collection.find().sort('inventory_number', 1)
        
        documents = [doc for doc in cursor]
        json_data = json.loads(json.dumps(documents, default=str))
        duration = time.time() - start
        return Response({"query_duration":duration, "query":json_data}, status=status.HTTP_202_ACCEPTED)

    
class UserQueryDetail(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        mongo = Mongo()
        
        search_piece = mongo.connect('pieces')
        _id = request.data.get('_id')
        cursor = search_piece.aggregate(pieceDetail(_id))
        
        documents = [doc for doc in cursor]                        
        json_detail = json.loads(json.dumps(documents, default=str))        

        modules = mongo.connect('modules')   

        cursor = modules.find(MODULES)
        documents = [doc for doc in cursor]                        
        json_modules = json.loads(json.dumps(documents, default=str)) 
        
        if not _id:
            return Response({'error': 'Missing _id in request'}, status=status.HTTP_410_GONE)        
        try:
            object_id = ObjectId(_id)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        if json_detail:
            response_data = {
                'detail': json_detail,
                'modules': json_modules
            }
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Piece not found'}, status=status.HTTP_404_NOT_FOUND)

    
class GenerateDetailPieceDocx(APIView):
    permission_classes = [IsAuthenticated]        
    
    def post(self, request): 
        _id = request.data.get('_id')
        mongo = Mongo()
        search_collection = mongo.connect('pieces_search')
        piece = search_collection.find_one({"_id":ObjectId(_id)})        
        if piece:
            template = DocxTemplate(settings.STATIC_PATH_DOCX + "detalle2.docx")            
            admitted_at = piece.get('admitted_at', None)
            if admitted_at is not None:
                # Calcula la diferencia en términos humanos
                admitted = Tools()                
                admitted_at_human = admitted.human_spanish_time(admitted_at)  #  humanize.naturaltime(datetime.now()-admitted_at)
            else: 
                admitted_at_human = "N/A"
            
            authors_info = piece.get('research_info', {}).get('authors_info', [])
            author_names = [author.get('title', '') for author in authors_info]
            author_names_str = ', '.join(author_names) if author_names else 'N/A'
            
            avaluo_value = piece.get('appraisal', 0.0)
            if isinstance(avaluo_value, Decimal128):
                avaluo_value = float(avaluo_value.to_decimal())
            else:
                avaluo_value = float(avaluo_value)            
            technique = piece.get('research_info', {}).get('technique', '')
            technique = html.escape(technique).replace('\n', '</w:t><w:br/><w:t>') if technique else "N/A"            
            materials = piece.get('research_info', {}).get('materials', '')
            materials = html.escape(materials).replace('\n', '</w:t><w:br/><w:t>') if materials else "N/A"            
            place_of = piece.get('research_info', {}).get('place_of_creation_info', [])            
            if place_of: 
                place_of_creation = ' '.join([place.get('title', '') for place in place_of])              
            else:
                place_of_creation = "N/A" 
                
            creation_date = piece.get('research_info', {}).get('creation_date', '')
            creation_date = html.escape(materials).replace('\n', '</w:t><w:br/><w:t>') if creation_date else "N/A"
            
            periods = piece.get('period_info', [])
            if periods:
                period_info = ' '.join([period.get('title', '') for period in periods])                                
            
            research_info = piece.get('research_info')            
            modules_collection = mongo.connect('modules')
            inventory_module = modules_collection.find_one({"name":"inventory"})            
            if inventory_module: 
                module_inventory_id = inventory_module['_id']                            
                photo_collection = mongo.connect('photographs')
                inventory_photos = photo_collection.find(
                    {
                    "piece_id":ObjectId(_id),
                    "module_id":ObjectId(module_inventory_id),
                    "deleted_at":{"$eq":None}
                    }                
                
                    )
                photos_inventory = []
                if inventory_photos: 
                    for photo in inventory_photos:
                        
                        image = settings.THUMBNAILS_INVENTORY_PATH + f"{photo['file_name']}"
                        photos_inventory.append(image)
                    
                    # Separar en grupos de 4 imágenes
                    split = 4
                    rows_array = [photos_inventory[i:i + split] for i in range(0, len(photos_inventory), split)]
                    # Imagen en blanco si no hay suficientes imágenes
                    empty_img = settings.BLANK_IMG  # Reemplaza con la ruta de tu imagen en blanco
                    
                     # Crear un contexto dinámico con filas de imágenes
                    inventory_images_context = []
                    for row in rows_array:
                        images_row = {
                            'iimga': InlineImage(template, row[0], width=Mm(20)) if len(row) > 0 else InlineImage(template, empty_img, width=Mm(20)),
                            'iimgb': InlineImage(template, row[1], width=Mm(20)) if len(row) > 1 else InlineImage(template, empty_img, width=Mm(20)),
                            'iimgc': InlineImage(template, row[2], width=Mm(20)) if len(row) > 2 else InlineImage(template, empty_img, width=Mm(20)),
                            'iimgd': InlineImage(template, row[3], width=Mm(20)) if len(row) > 3 else InlineImage(template, empty_img, width=Mm(20)),
                        }
                        inventory_images_context.append(images_row)
                  
            if research_info:
            
                context = {
                    'noInventario': piece.get('inventory_number', ''),
                    'noCatalogo': piece.get('catalog_number', ''),
                    'noProcedencia': piece.get('origin_number', ''),
                    'descripcion': piece.get('description_origin', ''),
                    'genero': piece.get('genders_info', {}).get('title', ''),  # Acceso seguro a genders_info.title
                    'subgenero': piece.get('subgenders_info', {}).get('title', ''),
                    'tipoObjeto': piece.get('type_object_info', {}).get('title', ''),
                    'materialDominante': piece.get('dominant_material_info', {}).get('title', ''),
                    'mueble': piece.get('tags', ''),
                    'avaluo': f"$ {format(avaluo_value, ',.2f')} USD",
                    'ubicacion': piece.get('location_info', {}).get('name', ''),
                    'fingreso': admitted_at_human,
                    'salto': piece.get('height', ''),
                    'sancho': piece.get('width', ''),
                    'sprofundo': piece.get('depth', ''),
                    'sdiametro': piece.get('diameter', ''),
                    'calto': piece.get('height_with_base', ''),
                    'sancho': piece.get('width_with_base', ''),
                    'sprofundo': piece.get('depth_with_base'),
                    'sdiametro': piece.get('diameter_with_base'),
                    'titulo': piece.get('research_info', {}).get('title', ''),
                    'autor': author_names_str,
                    'tecnica': technique,
                    'materiales': materials,
                    'procedencia': place_of_creation,
                    'images': inventory_images_context,
                    'fcreacion': creation_date,
                    'epoca': period_info,
                 }
            # Toma la plantilla y le pone los datos del contexto
            template.render(context)
            # Crea un archivo vacio de tipo BytesIO            
            doc_io = BytesIO()
            # Vuelca o salva el contenido del template en el archivo en blanco.
            template.save(doc_io)
            doc_io.seek(0)  # Mover el cursor al inicio del BytesIO   
            # Se forma la respuesta HTTP, y se le aplica el formato en este caso de word
            response = HttpResponse(doc_io, content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            # Se detalla en Content-Disposition para el navegador, que es un adjunto, y su nombre de arhivo
            response['Content-Disposition'] = "attachment; filename=detalle_pieza.docx"
            return response          
        return HttpResponse(status=400)


class Tools():
        
    def human_spanish_time(self, admitted_at):
        now = datetime.now()
        delta = now - admitted_at        
        seconds = delta.total_seconds()        
        minutes = seconds // 60        
        hours = minutes // 60
        days = hours // 24
        years = days // 365
        
        if years > 0:
            if years > 1:
                return f"hace {int(years)} años"        
            else:
                return f"hace {int(years)} año"        
        elif days > 0:
            if days > 1:
                return f"hace {int(days)} días"
            else:
                return f"hace {int(days)} día"                
        elif hours > 0:
            if hours > 1:
                return f"hace {int(hours)} horas"
            else:
                return f"hace {int(hours)} hora"                
        elif minutes > 0:
            if minutes > 1: 
                return f"hace {int(minutes)} minutos"
            else:
                return f"hace {int(minutes)} minuto"
        else:
            return "hace unos segundos"


class InventoryEdit(APIView):
    permission_classes = [IsAuthenticated]    
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    # authentication_classes = [JWTAuthentication]
    # En este metodo/verbo get obtenemos los datos para visualizarlos al editar
    def get(self, request, _id):
        
        mongo = Mongo()        
        
        inventoryChngapprov = mongo.connect("inventory_change_approvals")
        cursor_change = inventoryChngapprov.find_one({
            "piece_id":ObjectId(_id),
            "approved_rejected": None
                                           })     
        
        if cursor_change is None:
                           
            CollectionName = "pieces"
            piece = mongo.connect(CollectionName)
            cursor = piece.aggregate(inventory_edit(_id))            
            piece_array = [doc for doc in cursor]        
            piece_json = json.loads(json.dumps(piece_array, default=str))   
            piece_json = piece_json[0]            
            
            modules = mongo.connect('modules')
            cursor = modules.find_one({"name":"inventory"})            
            module = cursor       
            
            documents = mongo.connect('documents')
            cursor = documents.find({"module_id":module['_id'],
                                    "piece_id":ObjectId(_id),
                                    "deleted_at":None})
            documents = [doc for doc in cursor]
            json_documents = json.loads(json.dumps(documents, default=str))
            print("json_documents",json_documents)
            photographs = mongo.connect("photographs")
            cursor = photographs.find({"module_id": module['_id'],
                                    "piece_id":ObjectId(_id),
                                     "deleted_at": None})
            photographs = [doc for doc in cursor]
            json_pics = json.loads(json.dumps(photographs, default=str))
            
            genders = mongo.connect("genders")
            cursor = genders.find({"deleted_at":{"$eq": None}}).sort("title", 1)
            genders = [doc for doc in cursor]
            json_genders = json.loads(json.dumps(genders, default=str))
            
            subgenders = mongo.connect("subgenders")
            cursor = subgenders.find({"deleted_at":{"$eq": None}}).sort("title", 1)
            subgenders = [doc for doc in cursor]
            json_subgenders = json.loads(json.dumps(subgenders, default=str)) 
            
            object_type = mongo.connect("catalogs")
            cursor = object_type.find_one({"code": "object_type"})
            
            if cursor is not None:
                
                print("idObj", cursor["_id"])
                
                type_object_id = cursor["_id"]
                catalog_elements = mongo.connect("catalog_elements")
                cursor = catalog_elements.find({"catalog_id":ObjectId(type_object_id)})
                catalog_elements = [{"_id": doc["_id"], "title": doc["title"]} for doc in cursor]
                json_type_object = json.loads(json.dumps(catalog_elements, default=str))
                
            dominant_material = mongo.connect("catalogs")    
            cursor = dominant_material.find_one({"code":"dominant_material"})
            
            if cursor is not None:
                print("cur",cursor)
                dominant_material_id = cursor["_id"]
                catalog_elements = mongo.connect("catalog_elements")
                cursor = catalog_elements.find({"catalog_id":ObjectId(dominant_material_id)})
                catalog_elements = [{"_id": doc["_id"], "title": doc["title"]} for doc in cursor]
                json_dominant_material = json.loads(json.dumps(catalog_elements, default=str))
                           
            
            response_data = {
                "piece": piece_json,
                "documents": json_documents,
                "pics": json_pics,
                "genders": json_genders,
                "subgenders": json_subgenders,
                "type_object": json_type_object,
                "dominant_material": json_dominant_material,
                 
            }
                    
            return Response(response_data, status=status.HTTP_200_OK)
        
        else: 
            # Necesito ver en los permisos ya esta la funcion si tiene el permiso necesario para acreditar 
            # si puede aceptar los cambios, si no tiene ese permiso entonces debe poner un mensaje de que esta siendo editado y no se puede editar
            # hasta que se apruebe
            permissions = Permission()
            perm = permissions.get_permission(request.user)
            # Ya debe estar filtrado esto en el front end pero por refuerzo de seguridad 
            # le buscamos en la base de datos
            
            if "editar_inventario" in perm:
            
                data_to_approval = {}
                exclusions = {"created_at", "updated_at", "created_by", "_id", "approved_rejected_by", "approved_rejected"}                
                # Iteramos sobre cada clave-valor en `cursor_change`
                data_in_object = {"gender", "subgender"}
                
                for key, item in cursor_change.items():                    
                    # Filtramos las claves que queremos excluir
                    if key not in exclusions:
                        
                        if key in data_in_object:
                            
                            data_to_approval[key] = {
                                "oldValue": item["oldValue"]["title"],
                                "newValue": item["newValue"]["title"]                                
                            }
                                                        
                        else:
                        
                            data_to_approval[key] = item
                        
                        
                        
                
                
                data_to_approval["changes"] = True
                json_to_approval = json.loads(json.dumps(data_to_approval, default=str))
                return Response(json_to_approval, status=status.HTTP_200_OK)            
            else:
                return Response("You have not permission to approve", status=status.HTTP_401_UNAUTHORIZED)
            
            
    def generate_random_file(self, original_filename, length=40):
        #print("original_filename",original_filename)
        _, extension = os.path.splitext(original_filename)
        
        # Generar un nombre aleatorio con letras mayúsculas, minúsculas y números
        random_name = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
        # Devolver el nuevo nombre con la extensión original
        return f"{random_name}{extension}"
                        
    # Este metodo lo utilizamos para crear la colección de revisión
    # ya que en este sistema las modificaciones pasan primero por una inspección
    # si se acepta la modificacion esta se recibira en put
    def post(self, request, _id, *args, **kwargs):
        
        user_id = request.user.id
        
        mongo = Mongo()
        piece = mongo.connect("pieces")
        # piece_search = mongo.connect("pieces_search")        
        cursor = piece.find_one({"_id":ObjectId(_id)})
        print(cursor)
        changes = json.loads(request.data.get("changes", {}))
        #changes = json.loads(changes)
        print("changes",changes);
        
        changes_pics_info = json.loads(request.data.get("changes_pics_inputs", {}))        
        #changes_pics_info = json.loads(changes_pics_info)        
        for key, value in changes_pics_info.items():
            # Asegúrate de que `_id` sea una cadena antes de convertirla
            if '_id' in value and isinstance(value['_id'], str):
                value['_id'] = ObjectId(value['_id'])

        print(changes_pics_info)
        
        changed_pics = json.loads(request.data.get("changed_pics", "{}"))
        
        print("changed_pics",changed_pics)
        saved_files = []
        file_names = {}
        for key, meta in changed_pics.items():
            file = request.FILES.get(f"files[{key}]")  # Obtener archivo cargado
            if file:
                print("si hubo ")
                # Guardar el archivo en el sistema o base de datos según sea necesario
                # Ejemplo de guardar en una carpeta local
                try:
                    filename = self.generate_random_file(file.name)     
                    file_names[key] = filename
                    file_path = f"{settings.TEMPORARY_UPLOAD_DIRECTORY}{filename}"
                    with open(file_path, "wb") as f:
                        for chunk in file.chunks():
                            f.write(chunk)

                    # Guardar metadatos en una lista
                    saved_files.append({      
                        "key":key,              
                        "_id": ObjectId(meta["_id"]),                    
                        "file_name": filename,
                        "size": file.size,
                        "mime_type":file.content_type
                    })
                except Exception as e:
                    print(f"Error: is not posible to create the file ", e)
                
        print("Saved files:", saved_files)
        
        InventoryChanges = mongo.connect("inventory_change_approvals")
        if (changes and isinstance(changes, dict)) or (changes_pics_info and isinstance(changes_pics_info, dict)) or (changed_pics and isinstance(changed_pics, dict)):
            
            timestamps = AuditManager()                         
             
              # Combinar los diccionarios
            if changes_pics_info and isinstance(changes_pics_info, dict):
                               
                changes.update({"changed_pics_info":changes_pics_info})  # Agregar los campos de changes_pics_info a changes
                print("changes_update", changes)
            
            if changed_pics and isinstance(changed_pics, dict):
                for item in saved_files:
                    print("item",item["key"])
                    
                    changes.setdefault("changed_pics", []).append(item)                    
                    
                print("changes_pics", changes)  # Agregar los campos de changed_pics a changes             
             
            timestamped_changes = timestamps.add_timestamps(changes)
            timestamped_changes = timestamps.add_approvalInfo(timestamped_changes, user_id, _id)
            InventoryChanges.insert_one(timestamped_changes)
            
            for key, item in changes.items():
                print("key: ", key)
                
        else:
            print("El valor de 'changes' no es un diccionario.")
        
        if isinstance(changes_pics_info, dict):
            
            print(changes_pics_info)
            
        #gender_id = request.data.get("gender")       
        """
        for item in request.data:
            print(item)
            print(request.data.get(item))
        """ 
        return Response("is ok", status=status.HTTP_200_OK)
        
    def put(self, request, _id):
        
        user_id = request.user.id
        
        mongo = Mongo()
       
        changes = mongo.connect("inventory_change_approvals")        
        cursor_change = changes.find_one({"piece_id":ObjectId(_id),"approved_rejected":None})        
        exclusions = {"created_at", "updated_at", "created_by", "_id", "piece_id", "approved_rejected_by", "approved_rejected"} 
        id_change_fields = {"gender_id", "subgender_id",""}
       
        if cursor_change is not None:
            data_to_save = {}
            for key, item in cursor_change.items():                    
                # Filtramos las claves que queremos excluir                                                           
                if key not in exclusions:
                    
                    if key in id_change_fields:                        
                        data_to_save[key] = ObjectId(item["newValue"]["_id"])
                    else:                        
                        
                        data_to_save[key] = item["newValue"]                        
                                      
            #print(data_to_save)                
            try:
                is_approved = request.data.get("isApproved")
                print(is_approved)
                piece = mongo.connect("pieces")
                pieceStateBeforeChanges = piece.find_one({"_id":ObjectId(_id)})
                if is_approved:
                    cursor_piece = piece.update_one({"_id":ObjectId(_id)},
                                    {"$set": data_to_save})
                    if cursor_piece.matched_count > 0:
                        
                        pieces_search = mongo.connect("pieces_search")        
                        Pieces_one = PIECES_ALL        
                        Pieces_one.insert(0, { "$match": { "_id": ObjectId(_id) } }) 
                        #print("Pieces_one",Pieces_one)       
                        cursor = piece.aggregate(Pieces_one)
                        print("cursor",cursor)
                        for document in cursor:
                            print("document",document)
                            pieces_search.replace_one({'_id': ObjectId(_id)}, document)
                    
                    result = changes.update_one({"piece_id": ObjectId(_id),"approved_rejected": None},
                                    {"$set": {"approved_rejected_by":user_id,"approved_rejected": "approved"},
                                     "$push": {"piece_before_changes":pieceStateBeforeChanges}})
                    if result.modified_count > 0:
                        return Response("piece updated", status=status.HTTP_200_OK)     
                else:
                    result =changes.update_one({"piece_id": ObjectId(_id),"approved_rejected": None},
                                    {"$set": {"approved_rejected_by":user_id,"approved_rejected": "rejected"}})
                    if result.modified_count > 0:
                        return Response("piece rejected", status=status.HTTP_200_OK)                      
                                            
                
            except Exception as e:
                return Response(str(e), status=status.HTTP_400_BAD_REQUEST)        
    
    def patch(self, request):
        pass        
        
        
class AuditManager(): 
    mexico_tz = pytz.timezone('America/Mexico_City')

    def add_timestamps(self, object):
        object['created_at'] = datetime.now(self.mexico_tz)
        object['updated_at'] = datetime.now(self.mexico_tz)        
        return object
    
    def add_approvalInfo(self, object, user_id, _id):
        object['piece_id'] = ObjectId(_id)
        object['created_by'] = user_id
        object['approved_rejected_by'] = None
        object['approved_rejected'] = None
        return object
        
        
