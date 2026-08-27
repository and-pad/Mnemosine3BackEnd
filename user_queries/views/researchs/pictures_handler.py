
import os

from bson import ObjectId
from ..common.utils import generate_random_file_name, register_created_file
from django.conf import settings
#import mongo
#from user_queries.driver_database.mongo import Mongo
from user_queries.dataclasses.pictures import PicturesContext


def process_pictures(ctx: PicturesContext):
        # Process new pictures
        data = {}
        for index, pic in enumerate(ctx.pics_new):
            # Retrieve the file from the request
            if file := ctx.request.FILES.get(f"files[new_img_{index}]"):
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
                
                save_image_files(file, filename, ctx.created_files)
                        
        
        if ctx.changes_pics_inputs and len(ctx.changes_pics_inputs) > 0:
            data.setdefault("changes_pics_inputs", ctx.changes_pics_inputs)
            #save_image_inputs(request, changes_pics_inputs)          
        
        
        # Process changed pictures        
        for key, meta in ctx.changed_pics.items():
            # Retrieve the file from the request
            if file := ctx.request.FILES.get(f"files[changed_img_{key}]"):
                try:
                    # Generate a random file name
                    filename = generate_random_file_name(file.name)
                    # Save the file temporarily
                    save_image_files(file, filename, ctx.created_files)
                    # Append file details to saved_files
                    data.setdefault("changed_pics", []).append(
                        {
                            "key": key,
                            "_id": ObjectId(meta["_id"]),
                            "file_name": filename,
                            "size": file.size,
                            "mime_type": file.content_type,
                        }
                        
                    )
                except Exception as e:
                    # Log any errors encountered during file saving
                    print(
                        f"Error: is not possible to create the file, check the file permissions or the path: {e}"
                    )
                    raise
        return data
                    
                    
                    
def save_image_files(file, filename, created_files=None):
        file_path = f"{settings.PHOTO_RESEARCH_PATH}{filename}"
        try:
            with open(file_path, "xb") as f:
                for chunk in file.chunks():
                    f.write(chunk)
        finally:
            if os.path.isfile(file_path):
                register_created_file(file_path, created_files)
"""
def save_image_inputs(request, changes_pics_inputs):
    mongo = Mongo()    
    photo = mongo.connect("photographs")
    for pic in changes_pics_inputs:
        for element in pic:
            print("element", element)
"""
