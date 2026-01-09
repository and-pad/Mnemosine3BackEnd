from dataclasses import dataclass
from typing import Any, List, Dict
from bson import ObjectId

@dataclass
class DocumentsContext:
    request: Any
    changes_docs: List[dict]
    new_docs: List[dict]
    _id: ObjectId
    moduleId: ObjectId
    mongo: Any
    session: Any