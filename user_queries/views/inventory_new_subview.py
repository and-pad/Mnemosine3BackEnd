import json
import os
import shutil

from bson import ObjectId
from django.conf import settings
from PIL import Image

from user_queries.shemas.appraisal_shema import AppraisalSchema
from user_queries.shemas.document_shema import DocumentSchema
from user_queries.shemas.movements_shema import MovementsSchema
from user_queries.shemas.photograph_shema import PhotographSchema
from user_queries.shemas.piece_shema import PieceSchema
from user_queries.views.common.utils import (
    generate_random_file_name,
    get_catalog_elements,
    get_collection_json,
    get_locations,
    oid_list,
)
from user_queries.views.tools import AuditManager

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
    # data_get= list(mongo.connect("genders").find())
    response_data = {
        "genders": get_collection_json(mongo, "genders", {"deleted_at": None}, "title"),
        "subgenders": get_collection_json(
            mongo, "subgenders", {"deleted_at": None}, "title"
        ),
        "type_object": get_catalog_elements(mongo, "object_type"),
        "dominant_material": get_catalog_elements(mongo, "dominant_material"),
        "locations": get_locations(mongo),
    }

    return response_data


def process_post(request, mongo):
    user_id = request.user.id

    changes_raw = request.data.get("changes")
    if not changes_raw:
        return {}

    pics = json.loads(request.data.get("PicsNew", {}))

    if not pics:
        raise ValueError("No pictures provided: Is required at least one picture.")

    pics_info = _process_pics(pics, request)

    docs = json.loads(request.data.get("DocumentsNew", {}))
    docs_info = {}
    if docs:
        docs_info = _process_docs(docs, request)
    print("changes_raw:", changes_raw)
    changes = json.loads(changes_raw)

    inventory_fields = {}
    for field, payload in changes.items():
        inventory_fields[field] = payload.get("newValue")
    new_piece = {"new_piece": inventory_fields, **pics_info, **docs_info}
    audit = AuditManager()
    new_piece["approved_rejected_by"] = None
    new_piece["approved_rejected"] = None
    new_piece = audit.add_timestampsInfo(new_piece, ObjectId(user_id))

    with mongo.start_session() as session:
        try:
            with session.start_transaction():
                result = mongo.connect("inventory_change_approvals").insert_one(
                    new_piece, session=session
                )
        except Exception as e:
            print(f"Error al guardar cambios en la base de datos: {e}")
            raise e

    return result.inserted_id


def get_module_id(module_name, mongo, session):
    module = mongo.connect("modules").find_one({"name": module_name}, session=session)
    return module["_id"]


def _process_new_files(request, mongo, session, cursor_change, piece_id):

    # process new photos
    new_pics = cursor_change.get("new_pics", [])
    moduleId = get_module_id("inventory", mongo, session)
    for pic in new_pics:
        new_photo = {
            "photographer": pic["photographer"],
            "photographed_at": pic["photographed_at"] or None,
            "description": pic["description"],
            "file_name": pic["file_name"],
            "size": pic["size"],
            "mime_type": pic["mime_type"],
            "piece_id": ObjectId(piece_id),
            "module_id": ObjectId(moduleId),
        }
        try:
            origin_path = os.path.join(
                settings.TEMPORARY_UPLOAD_DIRECTORY, pic["file_name"]
            )
            destination_path = os.path.join(
                settings.PHOTO_INVENTORY_PATH, pic["file_name"]
            )
            shutil.move(origin_path, destination_path)
            img = Image.open(destination_path)
            width_thumbnail = 100
            height_thumbnail = int(img.height * (width_thumbnail / img.width))
            img_thumbnail = img.resize((width_thumbnail, height_thumbnail))
            img_thumbnail.save(settings.THUMBNAILS_INVENTORY_PATH + pic["file_name"])

            new_photo = AuditManager().add_timestampsInfo(
                new_photo, ObjectId(request.user.id)
            )
            new_photo = PhotographSchema(**new_photo).model_dump(exclude_none=False)
        except Exception as e:
            print(
                f"⚠️ Error processing photo, check file permissions '{pic['file_name']}': {e}"
            )
            raise e

        mongo.connect("photographs").insert_one(new_photo, session=session)

    # process new documents
    new_docs = cursor_change.get("new_docs", [])
    for doc in new_docs:
        new_document = {
            "name": doc["name"],
            "file_name": doc["file_name"],
            "size": doc["size"],
            "mime_type": doc["mime_type"],
            "piece_id": ObjectId(piece_id),
            "module_id": ObjectId(moduleId),
        }
        try:
            origin_path = os.path.join(
                settings.TEMPORARY_UPLOAD_DIRECTORY, doc["file_name"]
            )
            destination_path = os.path.join(
                settings.DOCUMENT_INVENTORY_PATH, doc["file_name"]
            )
            shutil.move(origin_path, destination_path)
            new_document = AuditManager().add_timestampsInfo(
                new_document, ObjectId(request.user.id)
            )
            new_document = DocumentSchema(**new_document).model_dump(exclude_none=False)
        except Exception as e:
            print(
                f"⚠️ Error processing document, check file permissions '{doc['file_name']}': {e}"
            )
            raise e

        mongo.connect("documents").insert_one(new_document, session=session)

        # Optionally, delete the temporary file after processing
        # os.remove(temp_file_path)


def process_put(request, mongo, session, cursor_change, _id):

    new_piece = cursor_change.get("new_piece")

    if "gender_id" in new_piece:
        new_piece["gender_id"] = ObjectId(new_piece["gender_id"]["_id"])
    if "subgender_id" in new_piece:
        new_piece["subgender_id"] = ObjectId(new_piece["subgender_id"]["_id"])
    if "location_id" in new_piece:
        new_piece["location_id"] = ObjectId(new_piece["location_id"]["_id"])
    if "type_object_id" in new_piece:
        new_piece["type_object_id"] = ObjectId(new_piece["type_object_id"]["_id"])
    if "dominant_material_id" in new_piece:
        new_piece["dominant_material_id"] = ObjectId(
            new_piece["dominant_material_id"]["_id"]
        )

    # new_piece["approved_rejected_by"] = request.user.id
    # new_piece["approved_rejected"] = True
    created_by = ObjectId(cursor_change.get("created_by"))
    new_piece = AuditManager().add_timestampsInfoNewInventory(
        new_piece, created_by, ObjectId(request.user.id)
    )

    new_piece = PieceSchema(**new_piece).model_dump(exclude_none=False)
    # Se crea la nueva pieza en la colección "pieces"
    Newpiece = mongo.connect("pieces").insert_one(new_piece, session=session)

    # Se crea el movimiento de entrada para la nueva pieza
    institution = mongo.connect("institutions").find_one(
        {"name": settings.INSTITUTION_NAME}
    )
    director_contact = mongo.connect("contacts").find_one(
        {"position": settings.POSITION_NAME_NEW_INVENTORY}
    )
    venue = mongo.connect("venues").find_one({"name": settings.INSTITUTION_NAME})
    # print("cursorchangE", cursor_change.get("new_piece", {}).get("location_id"))
    # print("cursorchangE", cursor_change.get("new_piece", {}).get("admitted_at"))
    # raise Exception("Debugging stop")
    admitedat = cursor_change.get("new_piece", {}).get("admitted_at")
    location_id = cursor_change.get("new_piece", {}).get("location_id")
    movement_doc = mongo.connect("movements").find_one(
        {}, sort=[("movements_id", -1)], projection={"movements_id": 1, "_id": 0}
    )
    if movement_doc:
        movements_id = movement_doc["movements_id"] + 1
    else:
        movements_id = 1

    movement_data = {
        "movement_id": movements_id,
        "movement_type": "internal",
        "itinerant": False,
        "institution_ids": oid_list(institution["_id"]),
        "venues": oid_list(venue["_id"]),
        "exhibition_id": location_id,
        "pieces_ids": oid_list(Newpiece.inserted_id),
        "pieces_ids_arrived": oid_list(Newpiece.inserted_id),
        "departure_date": admitedat,
        "contact_ids": oid_list(director_contact["_id"]),
        "guard_contact_ids": oid_list(director_contact["_id"]),
        "authorized_by_movements": ObjectId(request.user.id),
        # "created_by": ObjectId(request.user.id),
    }

    movement = MovementsSchema(
        **AuditManager().add_timestampsInfo(movement_data, ObjectId(request.user.id))
    ).model_dump(exclude_none=False)

    result_movement = mongo.connect("movements").insert_one(movement, session=session)
    print("Inserted movement ID:", result_movement.inserted_id)

    cursor_appraisal = cursor_change.get("new_piece", {}).get("appraisal", {})
    appraisal = {
        "appraisal": float(cursor_appraisal),
        "piece_id": Newpiece.inserted_id,
    }
    appraisal = AuditManager().add_timestampsInfo(appraisal, ObjectId(request.user.id))
    print("appraisal data:", appraisal)
    appraisal = AppraisalSchema(**appraisal).model_dump(exclude_none=False)
    mongo.connect("appraisal").insert_one(appraisal, session=session)

    # Se guardan los archivos asociados a la nueva pieza
    _process_new_files(request, mongo, session, cursor_change, Newpiece.inserted_id)

    mongo.connect("inventory_change_approvals").find_one_and_update(
        {"_id": ObjectId(_id), "approved_rejected": None},
        {
            "$set": {
                "piece_id": Newpiece.inserted_id,
                "approved_rejected_by": request.user.id,
                "approved_rejected": True,
            }
        },
        session=session,
    )
    # print("new_piece", new_piece)
    # result = mongo.connect("pieces").insert_one(new_piece, session=session)
    return Newpiece.inserted_id


def _process_pics(pics, request):

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
            print(pics_info, "test2")
            try:
                _save_temporary_files(file, filename)
            except Exception as e:
                print(f"⚠️ Error saving temporary file '{filename}': {e}")
                raise e
    print("pics_info so far:", pics_info)
    return pics_info


def _process_docs(docs, request):
    docs_info = {}
    for index, doc in enumerate(docs):
        if file := request.FILES.get(f"files[new_doc_{index}]"):
            filename = generate_random_file_name(file.name)
            docs_info.setdefault("new_docs", []).append(
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
