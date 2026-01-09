from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from bson import ObjectId

class VenuesSchema(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    institution_id: Optional[ObjectId] = None
    contact_id: Optional[ObjectId] = None
    start_venue: Optional[datetime] = None
    end_venue: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[ObjectId] = None
    updated_by: Optional[ObjectId] = None
    deleted_by: Optional[ObjectId] = None

    class Config:
        arbitrary_types_allowed = True 