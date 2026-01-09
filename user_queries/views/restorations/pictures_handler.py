
from bson import ObjectId
from ..common.utils import generate_random_file_name
from django.conf import settings
#import mongo
#from user_queries.driver_database.mongo import Mongo


def process_pictures(request, pics_new, changed_pics, changes_pics_inputs ):
        # Process new pictures
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
            
        for key, meta in changed_pics.items():
            # Retrieve the file from the request
            if file := request.FILES.get(f"files[changed_img_{key}]"):
                try:
                    # Generate a random file name
                    filename = generate_random_file_name(file.name)            
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
                    #save the file to the designated path
                    save_image_files(file, filename)
                except Exception as e:
                    # Log any errors encountered during file saving
                    print(
                        f"Error: is not possible to create the file, check the file permissions or the path: {e}"
                    )
        
        if changes_pics_inputs and len(changes_pics_inputs) > 0:
            data.setdefault("changes_pics_inputs", changes_pics_inputs)
        return data                    
                    
def save_image_files(file, filename):
        file_path = f"{settings.PHOTO_RESTORATION_PATH}{filename}"
        with open(file_path, "wb") as f:
            for chunk in file.chunks():
                f.write(chunk)

    