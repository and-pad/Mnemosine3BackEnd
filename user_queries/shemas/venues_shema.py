from pydantic import BaseModel, field_validator
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

    @field_validator("name", "address", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    class Config:
        arbitrary_types_allowed = True
