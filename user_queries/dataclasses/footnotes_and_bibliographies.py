from dataclasses import dataclass
from typing import Any, List, Dict
from bson import ObjectId

@dataclass
class FootnotesBibliographiesContext:
    request: Any
    _id: ObjectId
    new_footnotes: List[dict]
    new_bibliographies: List[dict]
    changes_bibliographies: List[dict]
    changes_footnotes: List[dict]
    mongo: Any
    session: Any

