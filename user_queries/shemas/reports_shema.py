from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from bson import ObjectId

class ReportsSchema(BaseModel):        
    name: Optional[str] = None
    description: Optional[str] = None
    columns: Optional[str] = None
    pieces_ids: Optional[list[ObjectId]] = None
    select_type: Optional[str] = None
    institution: Optional[str] = None
    exhibition: Optional[str] = None
    exhibition_date_end: Optional[datetime] = None
    exhibition_date_start: Optional[datetime] = None
    lending_list: Optional[bool] = None
    custom_order: Optional[bool] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    deleted_by: Optional[int] = None

    class Config:
        arbitrary_types_allowed = True
    