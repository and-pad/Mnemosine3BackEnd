from pydantic import BaseModel
from typing import Optional
from datetime import datetime
#from bson import ObjectId

class ModulesSchema(BaseModel):    
    name: Optional[str] = None
    label: Optional[str] = None
    active: Optional[bool] = None
    order: Optional[int] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    deleted_by: Optional[int] = None

    class Config:
        arbitrary_types_allowed = True