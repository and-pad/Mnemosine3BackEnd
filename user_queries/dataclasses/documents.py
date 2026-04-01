from dataclasses import dataclass, field
from typing import Any, List, Dict
from bson import ObjectId

@dataclass
class DocumentsContext:
    request: Any
    _id: ObjectId
    moduleId: ObjectId
    mongo: Any
    session: Any

    changes_docs: List[dict] = field(default_factory=list)
    new_docs: List[dict] = field(default_factory=list)