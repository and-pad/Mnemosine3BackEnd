#from bson import ObjectId

def getPermissions(user):
    permissions = [
            {'$match':{'model_id':user.id}},
            {                
                '$lookup':{
                    "from": "roles",
                    "localField": "role_id",
                    "foreignField": "id",
                    "as": "roles_info"                    
                    }                
                },
            {
                '$lookup':{
                    'from':'role_has_permissions',
                    'localField': 'roles_info.id',
                    'foreignField': 'role_id', 
                    'as': 'role_permissions_info'
                }                
            },
            {
                '$lookup':{
                    'from':'permissions',
                    'localField': 'role_permissions_info.permission_id',
                    'foreignField': 'id',
                    'as':'permissions_info'
                }
            },     
            {
                '$lookup':{
                    'from': 'user_has_permissions',
                    'localField': 'model_id',
                    'foreignField': 'model_id',
                    'as': 'user_has_permissions_info'
                }                
            },   
             {
                '$lookup':{
                    'from':'permissions',
                    'localField': 'user_has_permissions_info.permission_id',
                    'foreignField': 'id',
                    'as':'overwrite_permissions_info'
                }
            },                                  
                   ]
    return permissions