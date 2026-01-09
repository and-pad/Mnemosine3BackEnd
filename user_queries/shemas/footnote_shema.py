from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from bson import ObjectId

class FootNoteSchema(BaseModel):
    #bibliography_id: Optional[int] = None        
    title: Optional[str] = None    
    author: Optional[str] = None
    article: Optional[str] = None
    chapter: Optional[str] = None
    editorial: Optional[str] = None
    vol_no: Optional[str] = None
    city_country: Optional[str] = None
    pages: Optional[str] = None
    publication_date: Optional[str] = None
    description: Optional[str] = None    
    research_id: Optional[ObjectId] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[ObjectId] = None
    updated_by: Optional[ObjectId] = None
    deleted_by: Optional[ObjectId] = None   
    class Config:
        arbitrary_types_allowed = True