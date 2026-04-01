from pydantic import BaseModel, StringConstraints
from typing_extensions import Annotated

from typing import List, Optional, Literal
from datetime import datetime
from bson import ObjectId


NonEmptyStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1)
]

class PieceSchema(BaseModel):
    inventory_number: NonEmptyStr
    origin_number: NonEmptyStr
    catalog_number: NonEmptyStr

    appraisal: Optional[float] = None
    description_origin: Optional[str] = None
    gender_id: Optional[ObjectId] = None
    subgender_id: Optional[ObjectId] = None
    type_object_id: Optional[ObjectId] = None
    location_id: Optional[ObjectId] = None
    admitted_at: Optional[datetime] = None
    tags: Optional[str] = None
    height: Optional[float] = None
    width: Optional[float] = None
    depth: Optional[float] = None
    diameter: Optional[float] = None
    height_with_base: Optional[float] = None
    width_with_base: Optional[float] = None
    depth_with_base: Optional[float] = None
    diameter_with_base: Optional[float] = None
    base_or_frame: Literal['base', 'frame'] = 'base'
    research_info: Optional[bool] = False
    restoration_info: Optional[bool] = False
    in_exhibition: Optional[bool] = False
    dominant_material_id: Optional[ObjectId] = None
    description_inventory: Optional[str] = None
    documents_ids: Optional[List[ObjectId]] = None
    incidence: Optional[str] = None
    set_id: Optional[ObjectId] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[ObjectId] = None
    updated_by: Optional[ObjectId] = None
    deleted_by: Optional[ObjectId] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat() if v else None,
        }
    
    
    