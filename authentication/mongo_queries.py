from bson import ObjectId

def getPermissions(user):
    user_id = user.id if hasattr(user, "id") else user["_id"]
    permissions = [
            {'$match':{'model_id':ObjectId(user_id)}},
            {                
                '$lookup':{
                    "from": "roles",
                    "localField": "role_id",
                    "foreignField": "_id",
                    "as": "roles_info"                    
                    }                
                },
            {
                '$lookup':{
                    'from':'role_has_permissions',
                    'localField': 'roles_info._id',
                    'foreignField': 'role_id', 
                    'as': 'role_permissions_info'
                }                
            },
            {
                '$lookup':{
                    'from':'permissions',
                    'localField': 'role_permissions_info.permission_id',
                    'foreignField': '_id',
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
                    'foreignField': '_id',
                    'as':'overwrite_permissions_info'
                }
            },                                  
                   ]
    return permissions