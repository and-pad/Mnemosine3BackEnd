from pydantic import BaseModel
from typing import Optional
from datetime import datetime
#from bson import ObjectId

class CountriesSchema(BaseModel):    
    name: Optional[str] = None
    name_en: Optional[str] = None
    iso3: Optional[str] = None
    iso2: Optional[str] = None
    phonecode: Optional[str] = None
    capital: Optional[str] = None
    currency: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    flag: Optional[int] = None

    class Config:
        arbitrary_types_allowed = True
        