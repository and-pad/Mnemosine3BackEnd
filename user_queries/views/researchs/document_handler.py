


from bson import ObjectId
from pymongo.errors import PyMongoError
from ..common.utils import generate_random_file_name
from django.conf import settings
from user_queries.driver_database.mongo import Mongo
from ...shemas.document_shema import DocumentSchema
from ..tools import AuditManager
from ..common.utils import add_delete_to_actual_document_file_name
from user_queries.dataclasses.documents import DocumentsContext


#hay que quitar changes de aqui
def process_documents(ctx: DocumentsContext):
    
    changes_history = process_changed_docs(ctx.request,ctx.changes_docs, ctx.mongo, ctx.session)
    
    new_docs_history = process_new_docs(ctx.request, ctx.new_docs, ctx._id, ctx.moduleId, ctx.mongo, ctx.session)   
    
    return {"changes": changes_history, "new_docs": new_docs_history}
    
    
def save_doc_files(file, filename):
        
        file_path = f"{settings.DOCUMENT_RESEARCH_PATH}{filename}"
        with open(file_path, "wb") as f:
            for chunk in file.chunks():
                f.write(chunk)

def save_to_db(file, filename, name, _id, moduleId, user_id, mongo, session):
    """
    Guarda un documento en la colección 'documents'.

    Args:
        file: Objeto archivo cargado (con atributos `.size` y `.content_type`).
        filename (str): Nombre original del archivo.
        name (str): Nombre amigable para mostrar.
        _id (str): ID de la pieza relacionada.
        moduleId (str): ID del módulo relacionado.
        user_id (str): ID del usuario que inserta el documento.

    Returns:
        ObjectId: ID del documento insertado en MongoDB.

    Raises:
        ValueError: Si faltan parámetros requeridos.
        PyMongoError: Si ocurre un error al insertar en MongoDB.
    """
    
    if not all([file, filename, name, _id, moduleId, user_id]):
        raise ValueError("Todos los parámetros son obligatorios.")
    
    # Construcción del documento base
    document = {
        "name": name,
        "file_name": filename,
        "size": file.size,
        "mime_type": file.content_type,
        "piece_id": ObjectId(_id),
        "module_id": ObjectId(moduleId),
    }
    try:
        # Agregar información de auditoría, en este caso timestamps
        document = AuditManager().add_timestampsInfo(document, user_id)
        # Validar y preparar el esquema con Pydantic
        schema = DocumentSchema(**document).model_dump()
        # Insertar el documento en MongoDB
        result = mongo.connect("documents").insert_one(schema, session=session)
        # Leemos documento para historial
        inserted_doc = mongo.connect("documents").find_one({"_id": result.inserted_id}, session=session)
        
    except PyMongoError as e:
        raise PyMongoError(f"Error al insertar el documento en MongoDB: {e}")
    
    return inserted_doc



def update_to_db(meta, user_id, mongo, session, file=None, filename=None):
    """
    Actualiza un documento en la colección 'documents'.

    Args:
        meta (dict): Diccionario con la siguiente estructura:
            {
                "_id": str (ID del documento a actualizar),
                "name": dict (con claves "oldValue" y "newValue" para el nombre)
            }
        user_id (str): ID del usuario que actualiza el documento.
        file (Optional[UploadedFile]): Archivo cargado (con atributos `.size` y
            `.content_type`) para reemplazar el actual. Si no se proporciona, se
            actualizará solo el nombre del documento.
        filename (Optional[str]): Nombre del archivo cargado (si se proporciona).

    Returns:
        dict: Diccionario con los estados del documento antes y después de la
            actualización, con claves "before_update" y "after_update".

    Raises:
        ValueError: Si faltan parámetros requeridos.
        PyMongoError: Si ocurre un error al actualizar en MongoDB.
    """
    # Validación básica de parámetros
    if not meta or "_id" not in meta or "name" not in meta or "newValue" not in meta["name"]:
        raise ValueError("El parámetro 'meta' es inválido o incompleto.")
    if file and not filename:
        raise ValueError("Si se proporciona un archivo, también se debe proporcionar 'filename'.")
    if not user_id:
        raise ValueError("El parámetro 'user_id' es obligatorio.")

    # Construcción del documento a actualizar
    if file:
        document = {
            "name": meta["name"]["newValue"],
            "file_name": filename,
            "size": file.size,
            "mime_type": file.content_type,
        }
    else:
        document = {"name": meta["name"]["newValue"]}

    try:
        # Leer documento actual para historial
        before_update = mongo.connect("documents").find_one({"_id": ObjectId(meta["_id"])}, session=session)
        if not before_update:
            raise ValueError(f"No se encontró el documento con _id={meta['_id']}")

        # Agregar timestamps de actualización
        document = AuditManager().add_updateInfo(document, user_id)

        # Validar con Pydantic y excluir campos None
        schema = DocumentSchema(**document).model_dump(exclude_none=True)

        # Actualizar el documento en MongoDB
        result = mongo.connect("documents").update_one(
            {"_id": ObjectId(meta["_id"])},
            {"$set": schema},
            session=session
        )

        if result.matched_count == 0:
            raise PyMongoError(f"No se encontró ningún documento para actualizar con _id={meta['_id']}")

        # Leer documento actualizado para historial
        after_update = mongo.connect("documents").find_one({"_id": ObjectId(meta["_id"])},session=session)
        if not after_update:
            raise PyMongoError(f"Documento actualizado no se pudo leer después del update _id={meta['_id']}")

        return {"before_update": before_update, "after_update": after_update}

    except PyMongoError as e:
        raise PyMongoError(f"Error al actualizar el documento en MongoDB: {e}")


def process_new_docs(request, new_docs, _id, moduleId, mongo, session):
    """
    Procesa y guarda documentos nuevos asociados a una pieza.
    Si falla la inserción en la DB, aborta todo el proceso.

    Args:
        request: HttpRequest con los archivos en `FILES`.
        new_docs (list): Lista de dicts con info de cada doc (ej. [{"name": "..."}, ...]).
        _id (str): ID de la pieza.
        moduleId (str): ID del módulo.

    Returns:
        list: IDs de los documentos insertados en la base de datos.

    Raises:
        Exception: Si ocurre cualquier error durante la inserción en DB.
    """
    inserted_docs = []

    if new_docs and len(new_docs) > 0:
        for key, doc in enumerate(new_docs):
            if file := request.FILES.get(f"files[new_doc_{key}]"):
                # Generar nombre aleatorio para el archivo
                filename = generate_random_file_name(file.name)

                # Guardar el archivo físicamente
                save_doc_files(file, filename)

                # Guardar en la base de datos (si falla, aborta todo)
                doc_saved = save_to_db(
                    file, filename, doc["name"], _id, moduleId, ObjectId(request.user.id), mongo, session
                )
                inserted_docs.append(doc_saved)

    return inserted_docs
                
            


def process_changed_docs(request, changes_docs, mongo, session):
    """
    Procesa documentos modificados, actualizando su información en la base de datos
    y reemplazando archivos si se proporcionan.

    Args:
        request: HttpRequest con archivos en `FILES`.
        changes_docs (dict): Diccionario con los documentos a actualizar.
            Cada clave es un identificador único y el valor es un dict con metadatos:
            {
                "_id": str,
                "name": dict (con "oldValue" y "newValue")
            }

    Returns:
        dict: Diccionario con los documentos modificados bajo la clave
              'changed_documents'.

    Raises:
        ValueError: Si faltan parámetros esenciales.
        PyMongoError: Si ocurre un error al actualizar en MongoDB.
        OSError: Si ocurre un error al guardar archivos en el servidor.
    """
    if not changes_docs:
        return {"changed_documents": []}

    changed_documents = {}

    for key, meta in changes_docs.items():
        print("meta", meta)
        if "_id" not in meta:
            raise ValueError(f"Documento con key={key} no tiene _id.")

        # Procesar archivo si se subió uno
        if file := request.FILES.get(f"files[changed_doc_{key}]"):
            try:
                # Generar nombre aleatorio y guardar archivo físicamente
                print("file", file)
                filename = generate_random_file_name(file.name)
                save_doc_files(file, filename)

                # Marcar el archivo anterior como eliminado si aplica
                add_delete_to_actual_document_file_name(meta["_id"], "research")

                # Actualizar documento en DB
                changed_documents = update_to_db(meta, ObjectId(request.user.id), mongo, session, file, filename)
                print("changed_documents", changed_documents)
                # Agregar info al registro de cambios                

            except OSError as e:
                raise OSError(f"No se pudo guardar el archivo '{file.name}': {e}")
            except PyMongoError as e:
                raise PyMongoError(f"Error al actualizar el documento en MongoDB: {e}")

        else:
            # Solo cambio de metadatos (nombre)
            update_to_db(meta, ObjectId(request.user.id), mongo, session)
            changed_documents.setdefault("changed_documents", []).append(
                {
                    "key": key,
                    "_id": ObjectId(meta["_id"]),
                    "name": meta["name"],
                }
            )

    return changed_documents

    
    