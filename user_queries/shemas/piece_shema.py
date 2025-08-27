from pydantic import BaseModel
from typing import List, Optional, Literal
from datetime import datetime
from bson import ObjectId

class PieceSchema(BaseModel):
    inventory_number: Optional[str] = None
    origin_number: Optional[str] = None
    catalog_number: Optional[str] = None
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
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    deleted_by: Optional[int] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat() if v else None,
        }
    
    
    