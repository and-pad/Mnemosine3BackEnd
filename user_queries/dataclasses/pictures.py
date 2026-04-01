from dataclasses import dataclass, field
from typing import Any, List, Dict

@dataclass
class PicturesContext:
    request: Any
    pics_new: List[dict] = field(default_factory=list)
    changed_pics: Dict[str, dict] = field(default_factory=dict)
    changes_pics_inputs: List[dict] = field(default_factory=list)