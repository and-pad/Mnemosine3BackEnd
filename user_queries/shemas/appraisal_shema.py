from pydantic import BaseModel
from typing import Optional
from bson import ObjectId
from datetime import datetime

class AppraisalSchema(BaseModel):
    appraisal: Optional[float] = None
    piece_id: Optional[ObjectId] = None
    authorized_by: Optional[int] = None
    observation: Optional[str] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    deleted_by: Optional[int] = None
    class Config:
        arbitrary_types_allowed = True
    
    
    