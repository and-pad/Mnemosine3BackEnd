from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from bson import ObjectId

class RestorationsShema(BaseModel):
    preliminary_examination: Optional[str] = None
    laboratory_analysis: Optional[str] = None
    proposal_of_treatment: Optional[str] = None
    treatment_description: Optional[str] = None
    results: Optional[str] = None
    observations: Optional[str] = None
    treatment_date: Optional[datetime] = None
    responsible_restorer: Optional[ObjectId] = None
    piece_id: Optional[ObjectId] = None
    documents_ids: Optional[list[ObjectId]] = None
    photographs_ids: Optional[list[ObjectId]] = None
    height: Optional[float] = None
    width: Optional[float] = None
    depth: Optional[float] = None
    diameter: Optional[float] = None
    height_with_base: Optional[float] = None
    width_with_base: Optional[float] = None
    depth_with_base: Optional[float] = None
    diameter_with_base: Optional[float] = None
    base_or_frame: Optional[str] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[ObjectId] = None
    updated_by: Optional[ObjectId] = None
    deleted_by: Optional[ObjectId] = None
    class Config:
        arbitrary_types_allowed = True
    