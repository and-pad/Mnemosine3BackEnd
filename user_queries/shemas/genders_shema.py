from pydantic import BaseModel
from typing import Optional
from datetime import datetime
#from bson import ObjectId

class GendersSchema(BaseModel):    
    title: Optional[str] = None
    description: Optional[str] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    deleted_by: Optional[int] = None
    class Config:
        arbitrary_types_allowed = True