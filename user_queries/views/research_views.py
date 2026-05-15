import json
from bson import ObjectId
# from collections import defaultdict
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from user_queries.driver_database.mongo import Mongo

from rest_framework.permissions import IsAuthenticated
from .tools import AuditManager
from authentication.views import Permission
from user_queries.mongo_queries import (
    PIECES_ALL,
    inventory_research_edit,
    research_edit)

from types import SimpleNamespace

from user_queries.shemas.research_shema import ResearchSchema
from user_queries.shemas.photograph_shema import PhotographSchema

from .researchs.document_handler import process_documents
from .researchs.pictures_handler import process_pictures
from .researchs.footnotes_bibliographies_handler import process_footnotes_and_bibliographies
from .researchs.request_data_handler import load_request_data
from .researchs.save_history_handler import save_history_changes
from authentication.custom_jwt import CustomJWTAuthentication
from .common.utils import (
    format_new_pic, 
    get_research_id, 
    get_module_id, 
    process_thumbnail, 
    add_delete_to_actual_photo_file_name, 
    store_pic_changes, 
    format_research_data
    )
from user_queries.dataclasses.footnotes_and_bibliographies import FootnotesBibliographiesContext
from user_queries.dataclasses.documents import DocumentsContext
from user_queries.dataclasses.pictures import PicturesContext
from user_queries.dataclasses.research_inventory_data import ResearchInventoryContext
from user_queries.dataclasses.research_changes_data import ResearchContext
from user_queries.dataclasses.research_history_changes import HistoryChangesContext


class ResearchEdit(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    inventory_fields = [
        "gender_id",
        "subgender_id",
        "type_object_id",
        "dominant_material_id",
        "description_origin",
        "description_inventory",
    ]

    def get_request_permissions(self, request):
        permissions = Permission()
        return permissions.get_permission(request.user)

    def can_access_existing_research(self, request_permissions):
        return "editar_investigacion" in request_permissions

    def can_access_new_research(self, request_permissions):
        return (
            "agregar_investigacion" in request_permissions
            or "editar_investigacion" in request_permissions
        )

    

    def get_genders(self, mongo):
        """Obtiene todos los géneros en una sola consulta."""
        genders = mongo.connect("genders").find({"deleted_at": None}, {"title": 1})
        if not genders:
            return []

        genders = list(genders)
        return self.serialize_mongo_data(genders)

    def get_subgenders(self, mongo):
        """Obtiene todos los subgéneros en una sola consulta."""
        subgenders = mongo.connect("subgenders").find(
            {"deleted_at": None}, {"title": 1, "gender_id": 1}
        )
        if not subgenders:
            return []

        subgenders = list(subgenders)
        return self.serialize_mongo_data(subgenders)

    def get(self, request, _id):
        mongo = Mongo()
        module_id = get_module_id("research", mongo)
        if not module_id:
            return Response(
                {"response": "Módulo no encontrado"}, status=status.HTTP_400_BAD_REQUEST
            )

        research = list(
            mongo.connect("researchs").aggregate(research_edit(module_id, _id))
        )
        request_permissions = self.get_request_permissions(request)

        if research:
            if not self.can_access_existing_research(request_permissions):
                return Response(
                    {
                        "ok": False,
                        "message": "No tienes permiso para editar investigaciones",
                        "detail": "No tienes permiso para editar investigaciones",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif not self.can_access_new_research(request_permissions):
            return Response(
                {
                    "ok": False,
                    "message": "No tienes permiso para crear investigaciones",
                    "detail": "No tienes permiso para crear investigaciones",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        # print("research", research)

        cursor_change_json = {}
        if not research:

            print("No se encontraron registros de investigación... Creando uno nuevo")
            # Si no se encuentra investigación, se crea una nueva
            research = list(
                mongo.connect("pieces_search").aggregate(inventory_research_edit(_id))
            )
            cursor_change_json["inventory_data"] = json.loads(
                json.dumps(research, default=str)
            )
            # print("inventory data",cursor_change_json)
        else:

            cursor_change_json = json.loads(json.dumps(research, default=str))[0]

        # Obtener todos los catálogos en una sola consulta
        catalog_codes = [
            "author",
            "involved_creation",
            "place_of_creation",
            "period",
            "reference_type",
        ]
        catalog_ids = self.get_catalog_ids(mongo, catalog_codes)
        all_catalogs = {
            code: self.get_catalog_elements(mongo, catalog_id)
            for code, catalog_id in catalog_ids.items()
        }

        catalog_code = ["object_type", "dominant_material"]
        catalog_ids = self.get_catalog_ids(mongo, catalog_code)

        all_object_type = {
            code: self.get_catalog_elements(mongo, catalog_id)
            for code, catalog_id in catalog_ids.items()
        }

        researchs_documents = mongo.connect("documents").find(
            {"piece_id": ObjectId(_id), "deleted_at": None, "module_id": module_id}
        )
        researchs_documents = list(researchs_documents)
        cursor_change_json["documents"] = self.serialize_mongo_data(researchs_documents)

        researchs_photos = mongo.connect("photographs").find(
            {"piece_id": ObjectId(_id), "deleted_at": None, "module_id": module_id}
        )
        researchs_photos = list(researchs_photos)
        cursor_change_json["photos"] = self.serialize_mongo_data(researchs_photos)

        inv_modifications = list(
            mongo.connect("inventory_change_approvals").find(
                {"piece_id": ObjectId(_id), "approved_rejected": None}
            ))

        if inv_modifications:
            cursor_change_json["inventory_modifications"] = self.serialize_mongo_data(
                inv_modifications
            )
            # print("inv_modifications", cursor_change_json["inventory_modifications"])
        else:
            cursor_change_json["inventory_modifications"] = []

            # print("all_object_type",all_object_type.get("dominant_material", []))
        # print("period",period_research)
        return Response(
            {
                "research_data": cursor_change_json,
                "all_authors": all_catalogs.get("author", []),
                "all_involved_creation": all_catalogs.get("involved_creation", []),
                "all_place_of_creation": all_catalogs.get("place_of_creation", []),
                "all_period": all_catalogs.get("period", []),
                "all_genders": self.get_genders(mongo),
                "all_subgenders": self.get_subgenders(mongo),
                "all_object_type": all_object_type.get("object_type", []),
                "all_dominant_material": all_object_type.get("dominant_material", []),
                "all_references_type": all_catalogs.get("reference_type", []),
            },
            status=status.HTTP_200_OK,
        )

    def get_catalog_ids(self, mongo, catalog_codes):
        """Obtiene los ObjectId de los catálogos en una sola consulta."""
        catalogs = mongo.connect("catalogs").find(
            {"code": {"$in": catalog_codes}, "deleted_at": None}, {"code": 1, "_id": 1}
        )
        return {cat["code"]: cat["_id"] for cat in catalogs}

    def get_catalog_elements(self, mongo, catalog_id):
        """Obtiene todos los elementos de un catálogo por su ObjectId."""
        if not catalog_id:
            return []
        elements = list(
            mongo.connect("catalog_elements").find(
                {"catalog_id": ObjectId(catalog_id), "deleted_at": None}, {"title": 1}
            )
        )
        return self.serialize_mongo_data(elements)

    def get_research_data(self, mongo, data, field):
        """Obtiene los datos relacionados a un campo específico del research."""
        ids = data.get(field, [])
        if not isinstance(ids, list) or not ids:
            return []

        # Consulta optimizada para traer todos los elementos en una sola búsqueda
        elements = list(
            mongo.connect("catalog_elements").find(
                {"_id": {"$in": [ObjectId(i) for i in ids if ObjectId.is_valid(i)]}},
                {"_id": 1, "title": 1},
            )
        )
        return self.serialize_mongo_data(elements)

    def serialize_mongo_data(self, data):
        """Serializa datos de MongoDB a JSON serializable."""
        return json.loads(json.dumps(data, default=str))
        
    def patch_request_validation(self, request, _id, mongo):
        if not get_module_id("research", mongo):
            return Response(
                {"ok": False,
                 "message": "No se pudieron guardar los cambios",
                 "detail": "No se pudo encontrar el modulo de investigacion"}, status=status.HTTP_400_BAD_REQUEST                 
            )

        # Buscar investigación existente
        research = mongo.connect("researchs").find_one(
            {"piece_id": ObjectId(_id), "deleted_at": None}
        )
        request_permissions = self.get_request_permissions(request)

        if research:
            if not self.can_access_existing_research(request_permissions):
                return Response(
                    {
                        "ok": False,
                        "message": "No tienes permiso para editar investigaciones",
                        "detail": "No tienes permiso para editar investigaciones",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif not self.can_access_new_research(request_permissions):
            return Response(
                {
                    "ok": False,
                    "message": "No tienes permiso para crear investigaciones",
                    "detail": "No tienes permiso para crear investigaciones",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return research
    
    def validate_research(self, research, request, _id, mongo, session):
        is_new_research = False
        if not research:
            is_new_research = True
            timestamps = AuditManager()
            research_data = {"piece_id": ObjectId(_id)}
            research_data = timestamps.add_timestampsInfo(
                research_data, ObjectId(request.user.id)
            )             
            self.create_research(ResearchSchema(**research_data), mongo, session)
            research = mongo.connect("researchs").find_one(
                {"piece_id": ObjectId(_id), "deleted_at": None},
                session=session

            )

        return is_new_research, research

   


    def patch(self, request, _id):
        mongo = Mongo()
        with mongo.start_session() as session:
            try:
                with session.start_transaction():
        
                    research = self.patch_request_validation(request, _id, mongo)
                    if isinstance(research, Response):
                        return research

                    is_new_research, research = self.validate_research(research, request, _id, mongo, session)        
                    
                    (changes,
                     pics_new,
                     changed_pics,
                     changes_pics_inputs,
                     new_footnotes,
                     new_bibliographies,
                     changes_bibliographies,
                     changes_footnotes,
                     new_docs,
                     changes_docs
                     ) = load_request_data(request)
                    #print("raw changes_pics inputs", changes_pics_inputs)    
                    
                    ctx_fb = FootnotesBibliographiesContext(
                        request =                   request,
                        _id =                       ObjectId(_id),
                        new_footnotes =             new_footnotes,
                        new_bibliographies =        new_bibliographies,
                        changes_bibliographies =    changes_bibliographies,
                        changes_footnotes =         changes_footnotes,
                        mongo =                     mongo,
                        session =                   session
                        )                                       
                    
                    
                    ( ids_saved_footnotes,
                      ids_saved_bibliographies,
                      ids_updated_footnotes,
                      before_update_footnotes,
                      ids_updated_bibliographies,
                      before_update_bibliographies
                      # Procesa las notas al pie y bibliografías, guarda en la base de datos,
                      # regresa los ids de los nuevos y actualizados
                      ) = process_footnotes_and_bibliographies(ctx_fb)
                    
                    ctx_docs = DocumentsContext(
                        request =        request,
                        changes_docs =   changes_docs,
                        new_docs =       new_docs,
                        _id =            ObjectId(_id),
                        moduleId =       get_module_id("research", mongo),
                        mongo =          mongo,
                        session =        session
                    )                    
                    
                    # Procesa los documentos, guarda los archivos en el servidor,
                    # guarda en la base de datos, regresa los datos para el historial
                    documents = process_documents(ctx_docs)

                    ctx_pics = PicturesContext(
                        request =               request,                       
                        pics_new =              pics_new,
                        changed_pics =          changed_pics,
                        changes_pics_inputs =   changes_pics_inputs,                            
                    )

                    
                    # procesa las fotos, guarda los archivos en el servidor,
                    # regresa los datos para guardar en la base de datos
                    data_pics = process_pictures(ctx_pics)                    
                    # Si no hay cambios, no se hace nada
                    
                    user_id = request.user.id        
                
                    """
                    if changes_pics_inputs and len(changes_pics_inputs) > 0:
                        changes.setdefault("changes_pics_inputs", changes_pics_inputs)
                    """

                    ctx_re_inv = ResearchInventoryContext(
                        data =       changes,
                        user_id =    ObjectId(user_id),
                        _id =        ObjectId(_id),
                        mongo =      mongo,
                        session =    session
                    )

                    ctx_res = ResearchContext(
                        changes =            changes,
                        data_pics =          data_pics,
                        user_id =            ObjectId(user_id),
                        _id =                ObjectId(_id),
                        is_new_research =    is_new_research,
                        research =           research,  
                        mongo =              mongo,
                        session =            session
                    )

                    if changes or data_pics:
                        self.process_inventory_data(ctx_re_inv)
                        result = self.save_research_changes(ctx_res)

                    else:
                        result = SimpleNamespace(modified_count=0)            
                    
                    
                    ctx_history = HistoryChangesContext(
                        changes =                       changes,
                        data_pics =                     data_pics,
                        changes_pics_inputs =           changes_pics_inputs,
                        changed_pics =                  changed_pics,
                        new_footnotes =                 new_footnotes,
                        ids_saved_footnotes =           ids_saved_footnotes,
                        new_bibliographies =            new_bibliographies,
                        changes_footnotes =             changes_footnotes,
                        before_update_footnotes =       before_update_footnotes,
                        changes_bibliographies =        changes_bibliographies,
                        before_update_bibliographies =  before_update_bibliographies,
                        documents =                     documents,
                        _id =                           ObjectId(_id),
                        user_id =                       ObjectId(user_id),
                        research =                      research,
                        is_new_research =               is_new_research,
                        mongo =                         mongo,
                        session =                       session
                    )
     
                    
                    save_history_changes(ctx_history)
            
            except Exception as e:       
                # Si hubo error dentro del with start_transaction
                # Mongo aborta la transacción automáticamente.
                print(f"Error al procesar todo: {e}")
                raise


        print("research", research)
        return Response(
            {
                "ok": True,
                "message": "msg1ok",               
            },
            status=status.HTTP_200_OK,
        )


    def get_json_data(self, request, key, default={}):
        return json.loads(request.data.get(key, default))

    def process_changes(self, request, key):
        changes = self.get_json_data(request, key)
        for key, value in changes.items():
            if "_id" in value and isinstance(value["_id"], str):
                value["_id"] = ObjectId(value["_id"])
        print(changes)
        return changes

    def process_inventory_data(self, ctx: ResearchInventoryContext):        
        if inventoryData := {
            key: value
            for key, value in ctx.data.items()
            if key in self.inventory_fields
        }:            
            
            self.save_approval_inventory_data(inventoryData, ctx.user_id, ctx._id, ctx.mongo, ctx.session)

    def save_approval_inventory_data(self, data, user_id, _id, mongo, session):
        
        timestamps = AuditManager()

        try:

            InventoryChanges = mongo.connect("inventory_change_approvals")
            combined_changes = {}
            if data:
                combined_changes = {**combined_changes, **data}

            timestamped_changes = timestamps.add_timestampsUpdate(combined_changes)
            timestamped_changes = timestamps.add_approvalInfo(
                timestamped_changes, user_id, _id
            )
            timestamped_changes["changed_by_module_id"] = get_module_id("research", mongo)
            # Insert the timestamped changes into the inventory changes collection
            InventoryChanges.insert_one(timestamped_changes, session=session)

        except Exception as e:
            print(f"Error al guardar cambios en la base de datos: {e}")
            raise e

    def create_research(self, research_data: ResearchSchema, mongo , session):
        # Convertimos el objeto de Pydantic en diccionario limpio
        doc = research_data.model_dump(
            exclude_none=False
        )  # o exclude_defaults=True si quieres aún más limpio        
        researchs_collection = mongo.connect("researchs")
        result = researchs_collection.insert_one(doc, session=session)
        print("result create", result.inserted_id)
        return result

    def save_research_changes(self, ctx: ResearchContext):
        changes = ctx.changes
        data_pics = ctx.data_pics
        user_id = ctx.user_id
        _id = ctx._id
        is_new_research = ctx.is_new_research
        mongo = ctx.mongo
        session = ctx.session
        research = ctx.research        
        #research = mongo.connect("researchs").find_one({"piece_id": ObjectId(_id), "deleted_at": None} ,session=session)

        researchData = format_research_data(changes, self.inventory_fields )
        # Siempre agregar usuario que actualizó
        if not is_new_research:
            researchData["updated_by"] = ObjectId(user_id)
        print("researchData", researchData)
        # Aplicar actualización
        result = mongo.connect("researchs").update_one({"_id": research["_id"]}, {"$set": ResearchSchema(**researchData).model_dump(exclude_none=True)}, session=session)       
        self._process_all_pics(data_pics, user_id, _id, mongo, session)
        self._refresh_changes_in_db(_id, mongo, session)

        return result    
    
    def _refresh_changes_in_db(self, _id, mongo, session):
        piece = mongo.connect("pieces")
        pieces_search = mongo.connect("pieces_search")

        # Asegúrate de no mutar PIECES_ALL Global permanentemente
        pipeline = [{"$match": {"_id": ObjectId(_id)}}] + PIECES_ALL

        # Ejecutar el aggregate con sesión
        cursor = piece.aggregate(pipeline, session=session)

        for document in cursor:
            pieces_search.replace_one(
                {"_id": ObjectId(_id)},
                document,
                session=session
            )
        #mongo.checkAndDropIfExistCollection("pieces_search_serialized")
            
    def _process_all_pics(self, data_pics, user_id, _id, mongo, session):
        if data_pics.get("new_pics"):
            print("new_pics", data_pics["new_pics"])            
            self.process_new_pics(data_pics, user_id, _id, mongo, session)        
        
        if data_pics.get("changed_pics"):
            print("changed_pics", data_pics["changed_pics"])
            self.process_changed_pics(data_pics, user_id, mongo, session)


        if data_pics.get("changes_pics_inputs"):
            print("changes_pics_inputs", data_pics["changes_pics_inputs"])
            self.process_changed_pics_inputs(data_pics, user_id, mongo, session )
                # Aquí podrías procesar los cambios de entradas de fotos si es necesario
    def process_new_pics(self, cursor_change, user_id, _id, mongo, session):
        
        try:
            moduleId = get_module_id("research", mongo)   
            #print("cursor_change", cursor_change)
            if cursor_change.get("new_pics") and len(cursor_change["new_pics"]) > 0:
                for pic in cursor_change["new_pics"]:
                    # este es el objeto como debe ser guardado en la base, su shema.                                                             
                    result = mongo.connect("photographs").insert_one(PhotographSchema(**format_new_pic(pic, user_id, moduleId, _id)).model_dump(), session=session)                
                    pic["_id"] = result.inserted_id
                    process_thumbnail(pic, "research")               
        except Exception as e:
            print(f"Error al procesar nuevas fotos: {e}")
            # Habra errores en caso de falta de permisos o que no exista la carpeta
            # se debe corregir el error ya que no se puede guardar
            return e
        
   
    def process_changed_pics(self, cursor_change, user_id, mongo, session):
        
        try:
            #moduleId = get_module_id("research", mongo)
            #print("cursor_change", cursor_change["changed_pics"])
            for pic in cursor_change["changed_pics"]:
                photo_cursor = mongo.connect("photographs").find_one(
                    {"_id": ObjectId(pic["_id"])},
                    session=session
                )
                add_delete_to_actual_photo_file_name(photo_cursor["file_name"], "research")                
                store_pic_changes(pic, user_id, mongo, session)                
                process_thumbnail(pic, "research")
                #if cursor.modified_count > 0:
                    #print(f"Foto actualizada: {pic['_id']}")

        except Exception as e:
            print(f"Error al procesar fotos cambiadas: {e}")
    
    def process_changed_pics_inputs(self, cursor_change, user_id, mongo, session):      
        
        try:        
            for index,pic in cursor_change["changes_pics_inputs"].items():
                audit_pic = AuditManager()
                
                to_update = {
                "photographer": pic.get("photographer", {}).get("newValue") or None,
                "photographed_at": pic.get("photographed_at", {}).get("newValue") or None,
                "description": pic.get("description", {}).get("newValue") or None,
                }
                
                to_update = audit_pic.add_updateInfo(to_update, user_id)
                PhotographSchemaChanges = PhotographSchema(**to_update)
                print("pic_id", pic["_id"])
                print(PhotographSchemaChanges.model_dump(exclude_none=True))
                mongo.connect("photographs").update_one(
                    {"_id": ObjectId(pic["_id"])},
                    {
                        "$set": PhotographSchemaChanges.model_dump(exclude_none=True),
                    },
                    session=session
                )
                
        except Exception as e:
            print(f"Error al procesar entradas de fotos cambiadas: {e}")
