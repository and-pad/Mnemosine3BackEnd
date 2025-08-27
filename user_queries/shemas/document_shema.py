from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from bson import ObjectId

class DocumentSchema(BaseModel):    
    #bibliography_id: Optional[int] = None        
    name: Optional[str] = None
    file_name: Optional[str] = None
    size: Optional[int] = None
    mime_type: Optional[str] = None
    piece_id: Optional[ObjectId] = None
    module_id: Optional[ObjectId] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    deleted_by: Optional[int] = None
    class Config:
        arbitrary_types_allowed = True