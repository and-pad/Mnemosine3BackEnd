from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from bson import ObjectId

class MovementsSchema(BaseModel):
    
    movement_type: Optional[str] = None
    itinerant: Optional[bool] = None
    institution_ids: Optional[list[ObjectId]] = None
    contact_ids: Optional[list[ObjectId]] = None
    guard_contact_ids: Optional[list[ObjectId]] = None
    exhibition_id: Optional[ObjectId] = None
    venues: Optional[list[ObjectId]] = None
    departure_date: Optional[datetime] = None
    arrival_date: Optional[datetime] = None
    observations: Optional[str] = None
    start_exposure: Optional[datetime] = None
    end_exposure: Optional[datetime] = None
    pieces_ids: Optional[list[ObjectId]] = None
    authorized_by_movements: Optional[ObjectId] = None
    arrival_location_id: Optional[ObjectId] = None
    type_arrival: Optional[str] = None
    pieces_ids_arrived: Optional[list[ObjectId]] = None
    arrival_information: Optional[list[dict]] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[ObjectId] = None
    updated_by: Optional[ObjectId] = None
    deleted_by: Optional[ObjectId] = None

    class Config:
        arbitrary_types_allowed = True
    