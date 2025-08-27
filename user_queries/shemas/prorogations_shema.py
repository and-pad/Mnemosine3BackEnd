from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from bson import ObjectId

class ProrogationsSchema(BaseModel):
    movement_id: Optional[ObjectId] = None
    pieces_ids: Optional[list[ObjectId]] = None
    new_arrival_date: Optional[datetime] = None
    new_start_exhibition_date: Optional[datetime] = None
    new_end_exhibition_date: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    deleted_by: Optional[int] = None
    class Config:
        arbitrary_types_allowed = True
    