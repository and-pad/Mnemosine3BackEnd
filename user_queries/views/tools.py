import pytz
from datetime import datetime
from bson.objectid import ObjectId
from django.conf import settings



class AuditManager:
    
    tz = pytz.timezone( settings.AUDIT_MANAGER_TIME_ZONE)

    def add_timestampsUpdate(self, object):
        now = datetime.now(self.tz)
        if "created_at" not in object or object["created_at"] is None:        
            object["created_at"] = now        
        object["updated_at"] = now
        return object

    def add_approvalInfo(self, object, user_id, _id):
        object["piece_id"] = _id
        object["created_by"] = user_id
        object["approved_rejected_by"] = None
        object["approved_rejected"] = None
        return object

    def add_timestampsInfo(self, object, user_id):        
        object["created_by"] = user_id
        object["updated_by"] = None
        object["deleted_by"] = None
        object["created_at"] = datetime.now(self.tz)
        object["updated_at"] = None #datetime.now(self.tz)
        object["deleted_at"] = None

        return object
    
    def add_timestampsResearch(self, object, user_id, research, is_new_research):
        object["created_at"] = datetime.now(self.tz)        
        object["created_by"] = user_id
        if not is_new_research:            
            #object["updated_by"] = None
            #object["deleted_by"] = None
            #object["updated_at"] = None
            #object["deleted_at"] = None
        #else:
            object["research_before_changes"] = research
            #object["updated_by"] = user_id
            #object["updated_at"] = datetime.now(self.tz)

        return object
    
    

    def add_photoInfo(self, object, user_id):
        object = self.add_timestampsInfo(object, user_id)
        object["main_photogrphy"] = None
        return object
    


    def add_documentInfo(self, object, user_id):
        print("object in add_documentInfo", object)
        result = self.add_timestampsInfo(object, user_id)
        print("result", result)
        return result
    
    def add_updateInfo(self, object, user_id):
        #print("object in add_updateInfo", object)
        object["updated_by"] = user_id
        object["updated_at"] = datetime.now(self.tz)
        return object