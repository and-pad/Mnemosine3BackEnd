from pydantic import BaseModel, field_validator
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

    created_by: Optional[ObjectId] = None
    updated_by: Optional[ObjectId] = None
    deleted_by: Optional[ObjectId] = None

    @field_validator(
        "name",
        "last_name",
        "m_last_name",
        "position",
        "departament",
        "phone",
        "phone2",
        "email",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        if value is None:
            return value
        if "@" not in value:
            raise ValueError("El correo no es valido")
        return value

    class Config:
        arbitrary_types_allowed = True
