import sys
import os



sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from user_queries.driver_database.mongo import Mongo





    
class Permissions:
    
    def permissionsModel(self):
                        
        permissions = {
            "users": [
                
                'view_users',
                'add_users',
                'edit_users',
                'delete_users',
            ],
            "roles": [
                'view_roles',
                'add_roles',
                'edit_roles',
                'delete_roles',
            ],
            "inventory": [
                'view_inventory',
                'add_inventory',
                'edit_inventory',
                'delete_inventory',
            ],
            "research": [
                'view_research',
                'add_research',
                'edit_research',
                'delete_research',
            ],
            "restoration": [
                'view_restoration',
                'add_restoration',
                'edit_restoration',
                'delete_restoration',
            ],
            "movements": [
                'view_movements',
                'add_movements',
                'edit_movements',
                'delete_movements',
            ],
            "reports": [
                'view_reports',
                'add_reports',
                'edit_reports',
                'delete_reports',
            ],
            "settings": [
                'view_settings',
                'add_settings',
                'edit_settings',
                'delete_settings',
            ],
            "appraisals": [
                "view_appraisals",
                "add_appraisals",
                "edit_appraisals",
                "delete_appraisals",                
            ]
        }
        return permissions
    
    def createPermissions(self):
        permissions = self.permissionsModel()
        mongo = Mongo()
        
        mongo.checkAndDropIfExistCollection("user_permissions")            

        collection = mongo.connect('user_permissions')
        #print(permissions)
        list_names = []
        for name,permission_list in permissions.items():
            list_names.append(name)
            for permission in permission_list: 
                collection.insert_one({                    
                    "name": name,
                    "permission": permission,
                    
                    })
        for name in list_names:
            collection.insert_one({                
                "name": name,
            })
            
                                    

# Esto es para correrlo desde fuera de Django para crear los permisos
if __name__ == "__main__":
    permision = Permissions()
    permision.createPermissions();
    