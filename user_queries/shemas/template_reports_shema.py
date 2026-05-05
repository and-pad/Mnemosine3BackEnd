from datetime import datetime
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, field_validator


class TemplateReportsSchema(BaseModel):
    name: Optional[str] = None
    is_custom: Optional[bool] = None
    clm_ord: Optional[str] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[ObjectId] = None
    updated_by: Optional[ObjectId] = None
    deleted_by: Optional[ObjectId] = None

    @field_validator("name", "clm_ord", mode="before")
    @classmethod
    def normalize_string(cls, value):
        if value is None:
            return None
        return value.strip() if isinstance(value, str) else value

    class Config:
        arbitrary_types_allowed = True
