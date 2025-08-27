from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from bson import ObjectId

class CitiesSchema(BaseModel):    
    deleted_at: Optional[datetime] = None    
    name: Optional[str] = None
    state_id: Optional[ObjectId] = None
    country_id: Optional[ObjectId] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    flag: Optional[int] = None
    class Config:
        arbitrary_types_allowed = True

