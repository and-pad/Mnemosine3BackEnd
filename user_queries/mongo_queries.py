from bson import ObjectId
MODULES = {
    "deleted_at": None
}

def pieceDetail(_id):
    PIECE_DETAIL = [
        {"$match": {'_id': ObjectId(_id)}},
        {"$match": {"$expr": {"$eq": ["$deleted_at", None]}}},               
        {
            "$lookup": {
                "from": "genders",
                "localField": "gender_id",
                "foreignField": "_id",
                "as": "genders_info",
            }
        },
        {
            "$lookup": {
                "from": "subgenders",
                "localField": "subgender_id",
                "foreignField": "_id",
                "as": "subgenders_info",
            }
        },
        {
            "$lookup": {
                "from": "catalog_elements",
                "localField": "type_object_id",
                "foreignField": "_id",
                "as": "type_object_info",
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
                "from": "photographs",
                "let": {"piece_id": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$piece_id", "$$piece_id"]}}},
                    {"$match": {"$expr": {"$eq": ["$deleted_at", None]}}},
                    {
                        "$lookup": {
                            "from": "modules",
                            "localField": "module_id",
                            "foreignField": "_id",
                            "as": "module_info",
                        }
                    },
                    {"$match": {"module_info.name": "inventario"}},
                    {"$group": {"_id": "$_id", "photos": {"$push": "$$ROOT"}}},
                ],
                "as": "photo_info",
            }
        },
        {      
        "$lookup":{
            "from": "restorations",
            "let": {                
                "piece_id": "$_id"                
                },
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$piece_id", "$$piece_id"]}}},
                {"$match": {"$expr": {"$eq": ["$deleted_at", None]}}},
                {
                    "$lookup":{
                        "from": "catalog_elements",
                        "localField": "responsible_restorer",
                        "foreignField": "_id",
                        "as": "responsible_info",
                    }
                },                
                {
                 "$addFields": {                
                "responsible": {
                    "$mergeObjects": [
                        {
                            "title": {"$arrayElemAt": ["$responsible_info.title", 0]},
                            "restoration_id": "$_id" ,                            
                        }
                    ]
                },
                 },
                },                
            ],
            "as":"responsible_info"
        },
        },      
        {
            "$lookup": {
                "from": "researchs",
                "let": {"piece_id":"$_id"},
                "pipeline":[
                    {"$match":{"$expr":{"$eq":["$piece_id", "$$piece_id"]}}},
                    {"$match": {"$expr": { "$eq": ["$deleted_at", None] }}},                
                    {
                        "$lookup":{
                            "from":"bibliographies",
                            "let": {"research_id":"$_id"},
                            "pipeline":[
                                
                                {"$match":{"$expr":{"$eq":["$research_id","$$research_id"]}}},

                                {"$lookup":{
                                    "from": "catalog_elements",
                                    "localField": "reference_type_id",
                                    "foreignField":"_id",                                   
                                    "as": "reference_type_info",
                                }
                                },                                
                                {"$addFields":{
                                    "reference_type_info":"$reference_type_info.title",                                                                    
                                  }                                
                                },
                            ],                            
                            "as": "bibliographies_info",
                        }                        
                    }, 
                    {
                        "$lookup":{
                            "from":"catalog_elements",
                            "localField": "author_ids",
                            "foreignField": "_id",
                            "as":"author_info",
                        }
                    },
                    {
                        "$lookup":{
                            "from":"catalog_elements",
                            "localField": "set_id",
                            "foreignField": "catalog_elements_id",
                            "as":"set_info",
                        }
                    },
                    {
                        "$lookup":{
                            "from":"catalog_elements",
                            "localField": "involved_creation_ids",
                            "foreignField": "_id",
                            "as":"involved_creation_info",
                        }
                    },
                    {
                        "$lookup":{
                            "from":"catalog_elements",
                            "localField": "period_id",
                            "foreignField": "_id",
                            "as":"period_info",
                        }
                    },
                    {
                        "$lookup":{
                            "from":"catalog_elements",
                            "localField": "place_of_creation_id",
                            "foreignField": "_id",
                            "as":"place_of_creation_info",
                        }
                    },
                    {
                        "$lookup":{
                            "from":"footnotes",
                            "localField":"_id",
                            "foreignField":"research_id",
                            "as": "footnotes_info",
                        }                        
                    },                  
                    {
                        "$lookup":{
                            "from":"auth_user",
                            "localField":"created_by",
                            "foreignField":"id",
                            "as":"created_by_info"
                        }
                        
                    },                 
                    {
                        "$lookup":{
                            "from":"auth_user",
                            "localField":"updated_by",
                            "foreignField":"id",
                            "as":"updated_by_info",
                        }
                        
                    },                     
                    {"$addFields":{
                        "bibliographies_info": "$bibliographies_info",
                        "footnotes_info":"$footnotes_info",        
                        "authors_info": "$author_info",
                        "involved_creation_info": "$involved_creation_info",
                        "set_info": "$set_info",
                        "period_info": "$period_info",
                        "place_of_creation_info": "$place_of_creation_info",
                        "created_by_info": "$created_by_info.username",
                        "updated_by_info": "$updated_by_info.username",
                    }                     
                     },                                        
                ],                
                "as": "research_info",
            }
        },
        {
            "$lookup": {
                "from": "exhibitions",
                "localField": "location_id",
                "foreignField": "_id",
                "as": "location_info",
            }
        },
     {
    "$lookup": {
        "from": "appraisal",
        "let": {"piece_id": "$_id"},
        "pipeline": [
            {"$match": {"$expr": {"$eq": ["$piece_id", "$$piece_id"]}}},
            {"$match": {"$expr": { "$eq": ["$deleted_at", None] }}},            
            {
                "$lookup": {
                    "from": "auth_user",
                    "localField": "created_by",
                    "foreignField": "id",
                    "as": "user_info"
                }
            },
            {
                "$addFields": {
                    "user_info": {
                         "$mergeObjects": [
                        {
                            "username": {"$arrayElemAt": ["$user_info.username", 0]},
                            "email": {"$arrayElemAt": ["$user_info.email", 0]},                            
                        }
                        ]
                    }
                }
            },            
           {"$sort": {"created_at": -1, "appraisal_id": -1}},
        ],
        "as": "appraisalc_info"
    }
},
        {
            "$lookup": {
                "from": "restorations",
                "let": {"piece_id": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$piece_id", "$$piece_id"]}}},
                    {"$sort": {"treatment_date": -1}},
                    
                    {"$lookup":{
                        "from": "catalog_elements",
                        "localField": "responsible_restorer",
                        "foreignField": "_id",
                        "as":"responsible_info",                                              
                        }                     
                     },
                    {"$addFields":{
                        "responsible_info":{
                            "$mergeObjects":[
                                {
                                    "title":{"$arrayElemAt":["$responsible_info.title", 0]},                                    
                                }
                            ]
                        }
                        }},
                    
                ],
                "as": "restorations_info",
            }
        },        
             {
            "$lookup": {
                "from": "auth_user",
                "localField": "created_by",
                "foreignField": "id",
                "as": "created_by_piece_info",
            }            
        },
         {
            "$lookup": {
                "from": "auth_user",
                "localField": "updated_by",
                "foreignField": "id",
                "as": "updated_by_piece_info",
            }            
        },   
        {
    "$lookup": {
        "from": "movements",
        "let": { "piece_id": "$_id" },
        "pipeline": [
            {
                "$match": {
                    "$expr": {
                        "$and": [
                            { "$ne": ["$pieces_ids", None] },
                            { "$in": ["$$piece_id", "$pieces_ids"] }
                        ]
                    }
                }
            },
            {
                "$match": {
                    "$expr": { "$gt": ["$authorized_by_movements", 0] }
                }
            },
            {
                "$lookup": {
                    "from": "institutions",
                    "localField": "institution_ids",
                    "foreignField": "_id",
                    "as": "institutions_info"
                }
            },                     
            
            {
                "$lookup": {
                    "from": "exhibitions",
                    "localField": "exhibition_id",
                    "foreignField": "_id",
                    "as": "location_info",
                }
            },
             {
                "$lookup": {
                    "from": "venues",
                    "localField": "venues",
                    "foreignField": "_id",
                    "as": "venues_info",
                }
            },
            {"$addFields":{
                        "institutions_info":"$institutions_info.name",
                        "location_info": "$location_info.name",
                        "venues_info":"$venues_info.name",
            }
            },
            
            { "$sort": { "departure_date": -1 } },
            
            
        ],
        "as": "movements_info"
    }
},

              {
    "$lookup": {
        "from": "documents",
        "let": { "piece_id": "$_id" },
        "pipeline": [
            { "$match": { "$expr": 
                    { "$eq": ["$piece_id", "$$piece_id"] }
                 }
            },
            {"$match": {"$expr": { "$eq": ["$deleted_at", None] }}},
            {
                "$lookup":{
                    "from":"modules",
                    "localField": "module_id",
                    "foreignField":"_id",
                    "as":"module_info",
                }
            },
             {
                "$addFields": {
                    "module_info": "$module_info.name",
                    "module_id": "$module_info._id",                    
                }
             },
        ],
        "as": "documents_info",
        },
              },
        {
            "$addFields": {
                "genders_info": {
                    "$mergeObjects": [
                        {
                            "title": {"$arrayElemAt": ["$genders_info.title", 0]},
                            "description": {"$arrayElemAt": ["$genders_info.description", 0]}
                        }
                    ]
                },
                "subgenders_info": {
                    "$mergeObjects": [
                        {
                            "title": {"$arrayElemAt": ["$subgenders_info.title", 0]},
                            "description": {"$arrayElemAt": ["$subgenders_info.description", 0]}
                        }
                    ]
                },
                "dominant_material_info":{
                    "$mergeObjects":[
                        {
                            "title": {"$arrayElemAt": ["$dominant_material_info.title", 0]},
                            "description": {"$arrayElemAt": ["$dominant_material_info.description", 0]},                            
                        }
                        ],
                    },                    
                "type_object_info": {
                    "$mergeObjects": [
                        {
                            "title": {"$arrayElemAt": ["$type_object_info.title", 0]},
                            "description": {"$arrayElemAt": ["$type_object_info.description", 0]}
                        }
                    ]
                },
                "photo_info": "$photo_info.photos",
                "research_info": "$research_info",
                "location_info": {
                    "$mergeObjects": [
                        {
                            "name": {"$arrayElemAt": ["$location_info.name", 0]},
                        }
                    ]
                },
                "created_by_piece_info":{ 
                    "$mergeObjects":[
                        {
                            "username": {"$arrayElemAt": ["$created_by_piece_info.username", 0]},
                        }                        
                    ]},                
                "updated_by_piece_info":{ 
                    "$mergeObjects":[
                        {
                            "username": {"$arrayElemAt": ["$updated_by_piece_info.username", 0]},
                        }                        
                    ]},       
                "appraisalc_info": "$appraisalc_info",
                "restorations_info": "$restorations_info",
                "documents_info": "$documents_info",
                "responsible_info":{
                    "$mergeObjects": [
                        {                           
                            "responsible":{
                                "name":"$responsible_info.responsible.title",
                                "_id":"$responsible_info.responsible.restoration_id",                                
                                },                            
                        }
                    ]
                    },
                "first_movement": { "$arrayElemAt": ["$movements_info", 0] },
                "all_movements_info": "$movements_info",
            }
        }
    ]
    return PIECE_DETAIL 

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