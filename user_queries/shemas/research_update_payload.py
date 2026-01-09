from typing import Any, Optional
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId

class ResearchUpdatePayload(BaseModel):
    research_id: Optional[ObjectId] = None
    data_pics: Optional[Any] = None
    changes: Optional[Any] = None
    #changes_pics_inputs: Optional[Any] = None#
    #changed_pics: Optional[Any] = None#
    new_footnotes: Optional[Any] = None    
    new_bibliographies: Optional[Any] = None
    footnotes_data_changes: Optional[Any] = None
    bibliographies_data_changes: Optional[Any] = None
    research_before_update: Optional[Any] = None 
    documents: Optional[dict] = None
    created_at: Optional[datetime] = None    
    created_by: Optional[ObjectId] = None    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat() if v else None,
        }