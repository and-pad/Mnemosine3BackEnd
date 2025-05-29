import pytz
from datetime import datetime
from bson.objectid import ObjectId

class AuditManager:
    mexico_tz = pytz.timezone("America/Mexico_City")

    def add_timestamps(self, object):
        object["created_at"] = datetime.now(self.mexico_tz)
        object["updated_at"] = datetime.now(self.mexico_tz)
        return object

    def add_approvalInfo(self, object, user_id, _id):
        object["piece_id"] = ObjectId(_id)
        object["created_by"] = user_id
        object["approved_rejected_by"] = None
        object["approved_rejected"] = None
        return object

    def add_timestampsInfo(self, object, user_id):        
        object["created_by"] = user_id
        object["updated_by"] = None
        object["deleted_by"] = None
        object["created_at"] = datetime.now(self.mexico_tz)
        object["updated_at"] = None #datetime.now(self.mexico_tz)
        object["deleted_at"] = None

        return object
    
    def add_timestampsResearch(self, object, user_id, research, is_new_research):
        object["created_at"] = datetime.now(self.mexico_tz)        
        object["created_by"] = user_id
        if not is_new_research:            
            #object["updated_by"] = None
            #object["deleted_by"] = None
            #object["updated_at"] = None
            #object["deleted_at"] = None
        #else:
            object["research_before_changes"] = research
            #object["updated_by"] = user_id
            #object["updated_at"] = datetime.now(self.mexico_tz)

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