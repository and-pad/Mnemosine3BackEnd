#imports
import json
from bson import ObjectId
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .driver_database.mongo import Mongo
from .mongo_queries import * #PIECES_ALL, PIECE_DETAIL
import time


from django.conf import settings
from django.conf.urls.static import static

class UserQueryAll(APIView):    
    permission_classes = [IsAuthenticated]
    dbCollection = "pieces"
    dbCollectionPics = "photographs"
    def get(self, request):    
        mongo = Mongo()
        #collection = mongo.connect(self.dbCollection)#conectacon la base de datos y una coleccion en especifico y regresa el conector para ejecutar instrucciones
        start = time.time()
        #cursor = collection.aggregate(PIECES_ALL)#la instruccion viene de mongo_queries        
        
        search_collection = mongo.connect('pieces_search') 
        
        #for document in cursor:
            #search_collection.insert_one(document)        
        
        cursor = search_collection.find()
        documents =[doc for doc in cursor]                        
        json_data = json.loads(json.dumps(documents,default=str))        
        
        duration = time.time() - start
        
        return Response({"query_duration":duration,"query":json_data},status=status.HTTP_202_ACCEPTED)
    
class UserQueryDetail(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        mongo = Mongo()
        
        search_piece = mongo.connect('pieces')
        _id = request.data.get('_id')
        cursor = search_piece.aggregate(pieceDetail(_id))
        
        documents =[doc for doc in cursor]                        
        json_detail = json.loads(json.dumps(documents,default=str))        
        
        print(cursor)
        if not _id:
            return Response({'error': 'Missing _id in request'}, status=status.HTTP_410_GONE)
        
        try:
            object_id = ObjectId(_id)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        piece = search_piece.find_one({'_id': object_id})
        
        if piece:
            json_data = json.loads(json.dumps(piece, default=str))
            return Response(json_detail, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Piece not found'}, status=status.HTTP_404_NOT_FOUND)
            
        
        
        
        