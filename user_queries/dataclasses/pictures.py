from dataclasses import dataclass
from typing import Any, List, Dict
from bson import ObjectId

@dataclass
class PicturesContext:
    request: Any
    #_id: ObjectId
    pics_new: List[dict]
    changed_pics: List[dict]
    changes_pics_inputs: List[dict]    
    #mongo: Any
    #session: Any