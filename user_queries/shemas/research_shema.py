from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

class ResearchSchema(BaseModel):
    #researchs_id: Optional[int] = None
    title: Optional[str] = None
    author_ids: Optional[List[ObjectId]] = None
    set_id: Optional[int] = None
    technique: Optional[str] = None
    materials: Optional[str] = None
    period_id: Optional[ObjectId] = None
    creation_date: Optional[str] = None
    place_of_creation_id: Optional[ObjectId] = None
    acquisition_form: Optional[str] = None
    acquisition_source: Optional[str] = None
    acquisition_date: Optional[str] = None
    firm: Optional[bool] = None
    firm_description: Optional[str] = None
    short_description: Optional[str] = None
    formal_description: Optional[str] = None
    observation: Optional[str] = None
    publications: Optional[str] = None
    piece_id: Optional[ObjectId] = None
    card: Optional[str] = None
    involved_creation_ids: Optional[List[ObjectId]] = None
    keywords: Optional[str] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    deleted_by: Optional[int] = None
    
    class Config:
        arbitrary_types_allowed = True