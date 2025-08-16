from pydantic import BaseModel
from typing import List, Optional

class Example(BaseModel):
    query: str
    gold: Optional[str] = None
    sources: Optional[str] = ""
    negatives: Optional[List[str]] = []
