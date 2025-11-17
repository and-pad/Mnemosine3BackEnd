from hmac import new
from user_queries.driver_database.mongo import Mongo
from bson import ObjectId
from ..tools import AuditManager
from user_queries.shemas.bibliography_shema import BibliographySchema
from user_queries.shemas.footnote_shema import FootNoteSchema
from ..common.utils import get_research_id

def process_footnotes_and_bibliographies(request, _id, new_footnotes, new_bibliographies, changes_bibliographies, changes_footnotes):
        ids_saved_footnotes = None
        if new_footnotes and len(new_footnotes) > 0:            
            ids_saved_footnotes = save_new_footnotes(new_footnotes, request.user.id, _id)
            
        ids_saved_bibliographies = None        
        if new_bibliographies and len(new_bibliographies) > 0:
            ids_saved_bibliographies = save_new_bibliographies(new_bibliographies, request.user.id, _id)
        
        ids_updated_footnotes = None
        before_update_footnotes = None
        if changes_footnotes and len(changes_footnotes) > 0:
            ids_updated_footnotes, before_update_footnotes = update_footnotes(changes_footnotes, request.user.id, _id)
        ids_updated_bibliographies = None
        before_update_bibliographies = None
        if changes_bibliographies and len(changes_bibliographies) > 0:            
            ids_updated_bibliographies, before_update_bibliographies = update_bibliographies(changes_bibliographies, request.user.id, _id)
            
        return (
            ids_saved_footnotes,
            ids_saved_bibliographies,
            ids_updated_footnotes,
            before_update_footnotes,
            ids_updated_bibliographies,
            before_update_bibliographies,
        )
        
def save_new_footnotes(new_footnotes, user_id, _id):
    for footnote in new_footnotes:
    
        # Eliminar el campo original            
        research_id = get_research_id(_id) 
        footnote["research_id"] = ObjectId(research_id)
        footnote.pop("_id", None)  # Asegurarse de que no haya _id en el nuevo pie de página
        print("new_footnotes procesado:", new_footnotes)
    
    mongo = Mongo()
    # Agregar información de auditoría
    audit = AuditManager()
    ids_saved_footnotes = []
    for footnote in new_footnotes:
        footnote = audit.add_timestampsInfo(footnote, user_id)
        # Guardar en la colección de notas al pie
        try:
            footnote_shema = FootNoteSchema(**footnote)
            new_footnote = mongo.connect("footnotes").insert_one(footnote_shema.model_dump(exclude_none=False))
            print("new_footnote id", new_footnote.inserted_id)
        except Exception as e:
            print(f"Error al insertar nota al pie: {e}")
            continue
        # Agregar el ID del nuevo pie de página a la lista
        ids_saved_footnotes.append(new_footnote.inserted_id)
    
    return ids_saved_footnotes

def save_new_bibliographies(new_bibliographies, user_id, _id):
    mongo = Mongo()
    # Agregar información de auditoría
    audit = AuditManager()
    ids_saved_bibliographies = []
    for ind , bibliography in enumerate(new_bibliographies):
        
        # Extraer el primer id de reference_type_info y convertirlo a ObjectId
        print("index", ind)
        print("bibliography antes", bibliography)
        if "reference_type_info" in bibliography and bibliography["reference_type_info"]:
            
            ref_id_str = bibliography["reference_type_info"][0].get("_id")
            print("ref_id_str", ref_id_str)
            print("bibliography", bibliography)
            research_id = get_research_id(_id) 
            bibliography["research_id"] = ObjectId(research_id)
            if ref_id_str:
                bibliography["reference_type_id"] = ObjectId(ref_id_str)
                bibliography.pop("reference_type_info", None)

            
        bibliography.pop("_id", None)  # Asegurarse de que no haya _id en la nueva bibliografía
        print("bibliography despues", bibliography)   
        
        
        bibliography = audit.add_timestampsInfo(bibliography, user_id)
        # Guardar en la colección de bibliografías
        try:
            shema_bibliography = BibliographySchema(**bibliography)
            new_bibliography = mongo.connect("bibliographies").insert_one(shema_bibliography.model_dump(exclude_none=False))
        except Exception as e:
            print(f"Error al insertar bibliografía: {e}")
            continue
        # Agregar el ID de la nueva bibliografía a la lista
        ids_saved_bibliographies.append(new_bibliography.inserted_id)

    return ids_saved_bibliographies

def update_footnotes(changes_footnotes, user_id, _id):
        mongo = Mongo()
        audit = AuditManager()
        ids_saved_footnotes = []
        footnotes_before_update = []  # Ahora como lista estándar

        for index, footnote in changes_footnotes.items():
            data = {}
            footnote_id = footnote.get("_id")
            if not footnote_id:
                continue

            for key, value in footnote.items():
                if key == "_id":
                    continue
                # Campos normales
                if isinstance(value, dict) and "newValue" in value:
                    data[key] = value["newValue"]

            # Guardar estado anterior como parte de la lista
            old_footnote = mongo.connect("footnotes").find_one({"_id": ObjectId(footnote_id)})
            footnotes_before_update.append(old_footnote)

            if data:
                audit.add_updateInfo(data, user_id)

                result = mongo.connect("footnotes").update_one(
                    {"_id": ObjectId(footnote_id)},
                    {"$set": data}
                )

                print("Nota al pie actualizada:", footnote_id, "Modificaciones:", result.modified_count)
                ids_saved_footnotes.append(str(footnote_id))

        return ids_saved_footnotes, footnotes_before_update

    
    
def update_bibliographies( changes_bibliographies, user_id, _id):
    mongo = Mongo()
    audit = AuditManager()
    ids_saved_bibliographies = []
    bibliographies_before_update = []

    print("changes_bibliographies", changes_bibliographies)

    for index, bibliography in changes_bibliographies.items():
        data = {}

        bib_id = bibliography.get("_id")
        if not bib_id:
            continue  # Saltar si no hay _id

        for key, value in bibliography.items():
            if key == "_id":
                continue  # Saltar el _id

            # Tratamiento especial para reference_type_info
            if key == "reference_type_info":
                if (
                    isinstance(value, dict)
                    and "newValue" in value
                    and isinstance(value["newValue"], list)
                    and len(value["newValue"]) > 0
                    and "_id" in value["newValue"][0]
                ):
                    data["reference_type_id"] = ObjectId(value["newValue"][0]["_id"])
                continue  # Ya tratamos este campo

            # Campos normales
            if isinstance(value, dict) and "newValue" in value:
                data[key] = value["newValue"]
        
        # Guardar estado anterior como parte de la lista
        biblio_before_update = mongo.connect("bibliographies").find_one({"_id": ObjectId(bib_id)})
        bibliographies_before_update.append(biblio_before_update)
        if data:
            # Agrega updated_by y updated_at directamente al diccionario
            audit.add_updateInfo(data, user_id)

            result = mongo.connect("bibliographies").update_one(
                {"_id": ObjectId(bib_id)},
                {"$set": data}
            )

            print("Bibliografía actualizada:", bib_id, "Modificaciones:", result.modified_count)
            ids_saved_bibliographies.append(str(bib_id))

    return ids_saved_bibliographies, bibliographies_before_update