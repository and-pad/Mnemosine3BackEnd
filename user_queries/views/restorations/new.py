from hmac import new
from rest_framework.views import APIView
from user_queries.dataclasses.documents import DocumentsContext
from user_queries.driver_database.mongo import Mongo
from rest_framework.response import Response
from rest_framework import status

from user_queries.shemas.photograph_shema import PhotographSchema
from ...shemas.restorations_shema import RestorationsShema
import json
from bson import ObjectId
from user_queries.views.tools import AuditManager
from user_queries.views.common.utils import format_new_pic, format_restoration_data, generate_random_file_name, get_module_id, process_thumbnail
from rest_framework.permissions import IsAuthenticated
from authentication.custom_jwt import CustomJWTAuthentication
from .pictures_handler import process_pictures
from .document_handler import process_documents, process_new_docs
from user_queries.dataclasses.pictures import PicturesContext


class RestorationNew(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, _id):
        mongo = Mongo()


        piece = mongo.connect("pieces").find_one({"_id": ObjectId(_id)})
        if not piece:
            return Response("Piece not found", status=status.HTTP_404_NOT_FOUND)

        catalog_responsible_id = mongo.connect("catalogs").find_one({"code": "responsible_restorer"})["_id"] 
        catalog_responsible = list(mongo.connect("catalog_elements").find({"catalog_id": catalog_responsible_id}))                        
        catalog_responsible = json.loads(json.dumps(catalog_responsible, default=str))

        return Response({"catalog_responsible": catalog_responsible}, status=status.HTTP_200_OK)
    
    def post(self, request, _id):

        mongo = Mongo()       
        
        self.validate_request(request, _id, mongo)
        (data, pics_new, new_docs)= self.load_request(request, _id, mongo)
        
        with mongo.start_session() as session:
            try:
                with session.start_transaction():
                    
                    new_restoration_id = self.save_restoration(request, _id, data, pics_new, new_docs, mongo, session)



            except Exception as e:
                print(e)
                raise e

        
        return Response({}, status=status.HTTP_200_OK)



    def validate_request(self, request, _id, mongo):
        piece = mongo.connect("pieces").find_one({"_id": ObjectId(_id)})
        if not piece:
            return Response("Piece not found", status=status.HTTP_404_NOT_FOUND)
        
    def load_request(self, request, _id, mongo):
        changes = json.loads(request.data.get("formDatachanges", "{}"))    
        pics_new = json.loads(request.data.get("PicsNew", "{}"))    
        new_docs = json.loads(request.data.get("DocumentsNew", "{}"))    

        return (changes, pics_new, new_docs)
    
    def save_restoration(self, request, _id, data, pics_new, new_docs, mongo, session):        
        
        restoration = format_restoration_data(data)
        restoration["piece_id"] = ObjectId(_id)
        restoration["responsible_restorer"] = ObjectId(restoration["responsible_restorer"])

        restoration = AuditManager().add_timestampsInfo(restoration, ObjectId(request.user.id))
        restoration = RestorationsShema(**restoration).model_dump(exclude_none=False)       
        result = mongo.connect("restorations").insert_one(restoration, session=session)
        
        files_ids = self.process_files(request,_id, pics_new, new_docs, mongo, session)

        restoration["photographs_ids"] = files_ids["photographs_ids"]
        restoration["documents_ids"] = files_ids["documents_ids"]

        restoration = RestorationsShema(**restoration).model_dump(exclude_none=False)

        result2 = mongo.connect("restorations").update_one({"_id": result.inserted_id}, {"$set": restoration}, session=session)
        
        return result.inserted_id

        """
        restoration = RestorationsShema(**restoration)
        mongo.connect("restorations").insert_one(restoration.model_dump())
        """
    def process_files(self, request, _id, pics_new, new_docs, mongo, session):           

        ctx_pics = PicturesContext(request=request,  pics_new=pics_new)

        new_pics = process_pictures(ctx_pics)  
        photographs_ids = self.process_new_pics(new_pics, request.user.id, _id, mongo, session)

        """
        ctx_documents = DocumentsContext(
            request=request,
            changes_docs=new_docs,
            new_docs=new_pics, 
            _id=_id, 
            moduleId=get_module_id("restoration", mongo), 
            mongo=mongo, session=session
        )        
        """
        
        moduleId = get_module_id("restoration", mongo)

        documents_ids = process_new_docs(request, new_docs, _id, moduleId,  mongo,  session)

        return {"photographs_ids": photographs_ids, "documents_ids": documents_ids}



   
    def process_new_pics(self, data_pics, user_id, _id, mongo, session):
        photographs_ids = []
        print("data_pics", data_pics)
        if data_pics.get("new_pics"):
            #mongo = Mongo()
            moduleId = get_module_id("restoration", mongo)
        
            for new_pic in data_pics["new_pics"]:
                # este es el objeto como debe ser guardado en la base, su shema.                                                                           
                result = mongo.collection("photographs").insert_one(PhotographSchema(**format_new_pic(new_pic, ObjectId(user_id), moduleId, _id)).model_dump(), session=session)
                process_thumbnail(new_pic, "restoration")
                photographs_ids.append(result.inserted_id)
            
        return photographs_ids
    


    """
        data = {}
        print("pics_new", pics_new)
        for index, pic in enumerate(pics_new):
            # Retrieve the file from the request
            if file := request.FILES.get(f"files[new_img_{index}]"):
                # Generate a random file name
                filename = generate_random_file_name(file.name)
                # Add picture details to changes               
                data.setdefault("new_pics",[]).append(
                    {
                        "photographer": pic["photographer"],
                        "photographed_at": pic["photographed_at"],
                        "description": pic["description"],
                        "file_name": filename,
                        "size": pic["size"],
                        "mime_type": pic["mime_type"],
                    }
                )
                print("data", data)
                print("pic", pic)
                save_image_files(file, filename)
    """