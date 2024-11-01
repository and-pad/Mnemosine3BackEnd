# imports
import json
import html
import time
import locale
import humanize
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
from datetime import datetime, timezone
from docx.shared import Mm
from rest_framework_simplejwt.authentication import JWTAuthentication

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
        # collection = mongo.connect(self.dbCollection)#conectacon la base de datos y una coleccion en especifico y regresa el conector para ejecutar instrucciones                
        start = time.time()                
        # cursor = collection.aggregate(PIECES_ALL)#la instruccion viene de mongo_queries        
        search_collection = mongo.connect('pieces_search')        
        # for document in cursor:
            # search_collection.insert_one(document)        
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
            # Se detalla en Contente-Disposition para el navegador, que es un adjunto, y su nombre de arhivo
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
                                    "piece_id":ObjectId(_id)})
            documents = [doc for doc in cursor]
            json_documents = json.loads(json.dumps(documents, default=str))
            photographs = mongo.connect("photographs")
            cursor = photographs.find({"module_id": module['_id'],
                                    "piece_id":ObjectId(_id)})
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
            
            response_data = {
                "piece": piece_json,
                "documents": json_documents,
                "pics": json_pics,
                "genders": json_genders,
                "subgenders": json_subgenders
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
                for key, item in cursor_change.items():                    
                    # Filtramos las claves que queremos excluir
                    if key not in exclusions:
                        data_to_approval[key] = item
                        
                json_to_approval = json.loads(json.dumps(data_to_approval, default=str))
                return Response(json_to_approval, status=status.HTTP_200_OK)            
            else:
                return Response("You have not permission to approve", status=status.HTTP_401_UNAUTHORIZED)
                        
    # Este metodo lo vamos a utilizar para crear la colección de revisión
    # ya que en este sistema las modificaciones pasan primero por una inspección
    # si se acepta la modificacion esta se recibira en patch
    def post(self, request, _id):
        
        user_id = request.user.id
        
        mongo = Mongo()
        piece = mongo.connect("pieces")
        # piece_search = mongo.connect("pieces_search")        
        cursor = piece.find_one({"_id":ObjectId(_id)})
        print(cursor)
        changes = request.data.get("changes")
        InventoryChanges = mongo.connect("inventory_change_approvals")
        if isinstance(changes, dict):
            
            timestamps = AuditManager()
            timestamped_changes = timestamps.add_timestamps(changes)
            timestamped_changes = timestamps.add_approvalInfo(timestamped_changes, user_id, _id)
            InventoryChanges.insert_one(timestamped_changes)
            
            for key, item in changes.items():
                print("key: ", key)
                
        else:
            print("El valor de 'changes' no es un diccionario.")
                
        gender_id = request.data.get("gender")
        print("gender_id", gender_id)
        print(changes)
        print(_id)
        for item in request.data:
            print(item)
            print(request.data.get(item))
            
        return Response("is ok", status=status.HTTP_200_OK)
        
    def put(self, request, _id):
        
        user_id = request.user.id
        
        Pieces_one = PIECES_ALL        
        Pieces_one.insert(0, { "$match": { "_id": _id } })        
        
        mongo = Mongo()
        piece = mongo.connect("pieces")
        cursor = piece.aggregate(Pieces_one)        
        documents = None
        
        if cursor:
            for document in cursor:
                search_collection.insert_one(document)           
                
        mongo.connect("pieces_search")
        
        print(request._id)
        
        return Response("is ok", status=status.HTTP_200_OK)
    
    def patch(self, request):
        pass        
        
        
class AuditManager(): 

    def add_timestamps(self, object):
        object['created_at'] = datetime.now(timezone.utc)
        object['updated_at'] = datetime.now(timezone.utc)        
        return object
    
    def add_approvalInfo(self, object, user_id, _id):
        object['piece_id'] = ObjectId(_id)
        object['created_by'] = user_id
        object['approved_rejected_by'] = None
        object['approved_rejected'] = None
        return object
        
        
