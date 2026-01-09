from dataclasses import dataclass
from typing import Any, Dict, List
from bson import ObjectId

@dataclass
class HistoryChangesContext:    
    
    changes: List[dict]
    data_pics: Dict[str, Any]
    changes_pics_inputs: List[dict]
    changed_pics: List[dict]
    new_footnotes: List[dict]
    ids_saved_footnotes: List[ObjectId]
    new_bibliographies: List[dict]
    changes_footnotes: List[dict]
    before_update_footnotes: List[dict]
    changes_bibliographies: List[dict]
    before_update_bibliographies: List[dict]
    documents: List[dict]
    mongo: Any
    session: Any

    _id: ObjectId
    user_id: ObjectId
    research: dict
    is_new_research: bool