from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from bson import ObjectId

class ContactsSchema(BaseModel):    
    name: Optional[str] = None
    last_name: Optional[str] = None
    m_last_name: Optional[str] = None
    treatment_title: Optional[ObjectId] = None
    position: Optional[str] = None
    departament: Optional[str] = None
    phone: Optional[str] = None
    phone2: Optional[str] = None
    email: Optional[str] = None
    institution_id: Optional[ObjectId] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    deleted_by: Optional[int] = None

    class Config:
        arbitrary_types_allowed = True