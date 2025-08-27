from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from bson import ObjectId

class StatesSchema(BaseModel):
    name: Optional[str] = None
    country_id: Optional[ObjectId] = None
    flag: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    class Config:
        arbitrary_types_allowed = True