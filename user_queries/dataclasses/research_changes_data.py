from dataclasses import dataclass
from typing import Any, List, Dict
from bson import ObjectId

@dataclass
class ResearchContext:
    changes: List[dict]    
    data_pics: List[dict]
    user_id: ObjectId
    _id: ObjectId
    is_new_research: bool
    research: List[dict]
    mongo: Any
    session: Any
    created_files: List[str]
    moved_files: List[tuple[str, str]]
