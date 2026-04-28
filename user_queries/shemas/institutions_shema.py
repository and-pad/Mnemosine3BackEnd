from pydantic import BaseModel, field_validator
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
    created_by: Optional[ObjectId] = None
    updated_by: Optional[ObjectId] = None
    deleted_by: Optional[ObjectId] = None

    @field_validator(
        "name",
        "address",
        "city",
        "zip_code",
        "phone",
        "phone2",
        "fax",
        "email",
        "web_site",
        "business_activity",
        "rfc",
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

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value):
        if value is None:
            return value
        if len(value) < 7:
            raise ValueError("El numero de telefono debe contener al menos 7 caracteres")
        return value

    class Config:
        arbitrary_types_allowed = True
