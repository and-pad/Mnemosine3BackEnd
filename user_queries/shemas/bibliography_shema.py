from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from bson import ObjectId

class BibliographySchema(BaseModel):
    #bibliography_id: Optional[int] = None    
    reference_type_id: Optional[ObjectId] = None
    title: Optional[str] = None    
    author: Optional[str] = None
    article: Optional[str] = None
    chapter: Optional[str] = None
    editorial: Optional[str] = None
    vol_no: Optional[str] = None
    city_country: Optional[str] = None
    pages: Optional[str] = None
    editor: Optional[str] = None
    webpage: Optional[str] = None
    identifier: Optional[str] = None
    research_id: Optional[ObjectId] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    deleted_by: Optional[int] = None    
    class Config:
        arbitrary_types_allowed = True