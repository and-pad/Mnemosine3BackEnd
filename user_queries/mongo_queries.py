
"""En esta busqueda de Mongo lo que se hace es buscar todos los ids que hay en la tabla pieces
    Y extraemos sus datos para finalmente agregarlos como campos en la salida"""
PIECES_ALL = [
            
            {# lookup lo que hace es ver en otra collecion                 
                "$lookup": {
                    "from": "genders",# Aqui le ponemos el nombre de la colección a buscar
                    "localField": "gender_id",# el campo local de coincidencia 
                    "foreignField": "_id",# el campo foraneo de coincidencia
                    "as": "genders_info"# nombre como regresara las coincidencias 
                }
            },
            {                
                "$lookup": {
                    "from": "researchs",
                    "localField": "_id",
                    "foreignField": "piece_id",
                    "as": "research_info"
                }
            },
            {
                "$lookup": {
                    "from": "subgenders",
                    "localField": "subgender_id",
                    "foreignField": "_id",
                    "as": "subgenders_info"
                }
            },
            {
                "$lookup": {
                    "from": "catalog_elements",
                    "localField": "type_object_id",
                    "foreignField": "_id",
                    "as": "type_object_info"
                }
            },
            {
                "$lookup": {
                    "from": "catalogs",
                    "localField": "type_object_info.catalog_id",
                    "foreignField": "_id",
                    "as": "catalog_type_object_info"
                }
            },
            {
                "$lookup": {
                    "from": "exhibitions",
                    "localField": "location_id",
                    "foreignField": "_id",
                    "as": "location_info"
                }
            },
            {
                "$lookup": {
                    "from": "institutions",
                    "localField": "location_info.institution_id",
                    "foreignField": "_id",
                    "as": "institutions_info"
                }
            },
            
            {
                "$lookup": {
                    "from": "catalog_elements",
                    "localField": "dominant_material_id",
                    "foreignField": "_id",
                    "as": "dominant_material_info"
                }
            },
            {
                "$lookup": {
                    "from": "catalogs",
                    "localField": "dominant_material_info.catalog_id",
                    "foreignField": "_id",
                    "as": "catalog_dominant_material_info"
                }
            },            
            {
                "$lookup": {
                    "from": "catalogs",
                    "localField": "type_object_info.catalog_id",
                    "foreignField": "_id",
                    "as": "catalog_type_object_info"
                }
            },   
            
            {
                "$lookup": {# este campo tiene guardado como string separado por comas los ids lo que requiere otro procesamiento
                    "from": "catalog_elements",
                    "localField": "research_info.author_ids",
                    "foreignField": "_id",
                    "as": "authors_info"
                }
            },
            {
                "$lookup": {
                    "from": "catalog_elements",
                    "localField": "research_info.period_id",
                    "foreignField": "_id",
                    "as": "period_info"
                }
            },
            
            {
                "$lookup": {
                    "from": "catalog_elements",
                    "localField": "research_info.involved_creation_ids",
                    "foreignField": "_id",
                    "as": "involved_creation_info"
                }
            },
            
          {
    "$lookup": {
        # El lookup de fotografías necesita de otros 'modules' para extraer el thumbnail
        # adecuado en este caso de inventario, ya que el numero de pieza se puede repetir en otro modulo (en otra busqueda),
        # Se busca en la colección de fotografías
        "from": "photographs",
        # Se define la variable local para la comparación
        "let": { "piece_id": "$_id" },
        "pipeline": [
            # Se realiza la coincidencia basada en la variable local
            {
                "$match": {
                    "$expr": { "$eq": ["$piece_id", "$$piece_id"] }
                }
            },
            {
                "$match": {
                    "$expr": { "$eq": ["$deleted_at", None] }
                }
            },
            # Se realiza un segundo lookup con la colección de módulos
            
            {
                "$lookup": {
                    "from": "modules",
                    "localField": "module_id",
                    "foreignField": "_id",
                    "as": "module_info"
                }
            },
            # Se filtra para obtener solo los módulos de nombre "inventario"
            {
                "$match": {
                    "module_info.name": "inventario"
                }
            },
            # Se limita el resultado a solo uno
            {
                "$limit": 1 
            }
        ],
        # Se asigna el resultado al campo "photo_thumb_info"
        "as": "photo_thumb_info"
    }
},                       
            
            {
                "$addFields": {
                    
                      
                      
                    "period_info":{
                        "$map": {
                                "input": "$period_info",
                                "as": "period",
                                "in": {
                                    "title": "$$period.title",                                   
                                
                        }
                    }
                        },
                    
                    
                    "involved_creation_info":{
                        "$map": {
                                "input": "$involved_creation_info",
                                "as": "involved",
                                "in": {
                                    "title": "$$involved.title",                                   
                                
                        }
                    }
                        },
                    
                    "authors_info": {
                            "$map": {
                                "input": "$authors_info",
                                "as": "author",
                                "in": {
                                    "title": "$$author.title",                                   
                                
                        }
                    }
                },
                            
                    "research_info":{
                        "$mergeObjects": [
                            {
                                "title": { "$arrayElemAt": ["$research_info.title", 0] },
                                "keywords": { "$arrayElemAt": ["$research_info.keywords", 0] },                                
                                "technique": { "$arrayElemAt": ["$research_info.technique", 0] },
                                "materials": { "$arrayElemAt": ["$research_info.materials", 0] },
                                "acquisition_form": { "$arrayElemAt": ["$research_info.acquisition_form", 0] },
                                "acquisition_source": { "$arrayElemAt": ["$research_info.acquisition_source", 0] },
                                "acquisition_date": { "$arrayElemAt": ["$research_info.acquisition_date", 0] },
                                "firm_description": { "$arrayElemAt": ["$research_info.firm_description", 0] },
                                "short_description": { "$arrayElemAt": ["$research_info.short_description", 0] },
                                "formal_description": { "$arrayElemAt": ["$research_info.formal_description", 0] },
                                "observation": { "$arrayElemAt": ["$research_info.observation", 0] },
                                "publications": { "$arrayElemAt": ["$research_info.publications", 0] },
                                "card": { "$arrayElemAt": ["$research_info.card", 0] },
                                
                            },
                           
                        ]
                    },
                        "photo_thumb_info": {
                            "$mergeObjects": [
                            {
                                "file_name": { "$arrayElemAt": ["$photo_thumb_info.file_name", 0] },
                            },
                            ]
                          
                      },
                    "genders_info": {
                        "$mergeObjects": [
                            {
                                "title": { "$arrayElemAt": ["$genders_info.title", 0] },
                                "description": { "$arrayElemAt": ["$genders_info.description", 0] }
                            },
                           
                        ]
                    },
                    "subgenders_info": {
                        "$mergeObjects": [
                            {
                                "title": { "$arrayElemAt": ["$subgenders_info.title", 0] },
                                "description": { "$arrayElemAt": ["$subgenders_info.description", 0] }
                            },
                           
                        ]
                    },
                    "type_object_info": {
                        "$mergeObjects": [
                            {
                                "title": { "$arrayElemAt": ["$type_object_info.title", 0] },
                                "description": { "$arrayElemAt": ["$type_object_info.description", 0] }
                            },
                           
                        ]
                    },                    
                    "catalog_type_object_info":{
                        "$mergeObjects": [
                            {
                                "code": { "$arrayElemAt": ["$catalog_type_object_info.title", 0] },
                                "title": { "$arrayElemAt": ["$catalog_type_object_info.description", 0] }
                            },                           
                        ]
                    },                    
                    "location_info" : {
                        "$mergeObjects": [
                            {
                                "name": { "$arrayElemAt": ["$location_info.name", 0] },                                
                            },                           
                        ]
                    },                    
                    "dominant_material_info":{
                        "$mergeObjects": [
                            {
                                "title": { "$arrayElemAt": ["$dominant_material_info.title", 0] },
                                "description": { "$arrayElemAt": ["$dominant_material_info.description", 0] }
                            },                           
                        ]
                    },                        
                    "catalog_dominant_material_info" :{
                        "$mergeObjects": [
                            {
                                "code": { "$arrayElemAt": ["$catalog_dominant_material_info.code", 0] },                                
                                "title": { "$arrayElemAt": ["$catalog_dominant_material_info.title", 0] },                                
                            },
                           
                        ]
                    },                    
                    "institutions_info" : {
                        "$mergeObjects": [
                            {
                                "name": { "$arrayElemAt": ["$institutions_info.name", 0] },
                                "city": { "$arrayElemAt": ["$institutions_info.city", 0] },    
                                "business_activity": { "$arrayElemAt": ["$institutions_info.business_activity", 0] },    
                                "web_site": { "$arrayElemAt": ["$institutions_info.web_site", 0] },
                            },                           
                        ]
                    },                    
                }
            }
            ]
