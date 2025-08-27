from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from bson import ObjectId


class InstitutionsSchema(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country_id: Optional[ObjectId] = None
    state_id: Optional[ObjectId] = None
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    phone2: Optional[str] = None
    fax: Optional[str] = None
    email: Optional[str] = None
    web_site: Optional[str] = None
    business_activity: Optional[str] = None
    rfc: Optional[str] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    deleted_by: Optional[int] = None

    class Config:
        arbitrary_types_allowed = True