
from bson import ObjectId
from ..common.utils import generate_random_file_name
from django.conf import settings
#import mongo
from user_queries.driver_database.mongo import Mongo


def process_pictures(request, pics_new, changed_pics, changes_pics_inputs ):
        # Process new pictures
        data = {}
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
                
                save_image_files(file, filename)
                        
        
        if changes_pics_inputs and len(changes_pics_inputs) > 0:
            data.setdefault("changes_pics_inputs", changes_pics_inputs)
            #save_image_inputs(request, changes_pics_inputs)
            
        
        
        # Process changed pictures        
        for key, meta in changed_pics.items():
            # Retrieve the file from the request
            if file := request.FILES.get(f"files[changed_img_{key}]"):
                try:
                    # Generate a random file name
                    filename = generate_random_file_name(file.name)
                    # Save the file temporarily
                    save_image_files(file, filename)
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
        return data
                    
                    
                    
def save_image_files(file, filename):
        file_path = f"{settings.PHOTO_RESEARCH_PATH}{filename}"
        with open(file_path, "wb") as f:
            for chunk in file.chunks():
                f.write(chunk)
"""
def save_image_inputs(request, changes_pics_inputs):
    mongo = Mongo()    
    photo = mongo.connect("photographs")
    for pic in changes_pics_inputs:
        for element in pic:
            print("element", element)
"""
    
    