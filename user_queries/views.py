#imports
import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .driver_database.mongo import Mongo
from .mongo_queries import *
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
        
        