
from dataclasses import dataclass
from typing import Any, List, Dict
from bson import ObjectId

@dataclass
class ResearchInventoryContext:
    data: List[dict]    
    user_id: ObjectId
    _id: ObjectId
    mongo: Any
    session: Any