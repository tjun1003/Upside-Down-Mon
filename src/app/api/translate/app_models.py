from typing import Any, Dict, List, Optional

from pydantic import BaseModel

class ChatRequest(BaseModel):
    session_id: str = "default"
    message: str
    target_lang: str = "auto"
    assistant_mode: bool = True
    independent_langs: Optional[List[str]] = None


class DetectRequest(BaseModel):
    text: str


class KBAddRequest(BaseModel):
    documents: List[Dict[str, Any]]


class ClearRequest(BaseModel):
    session_id: str = "default"
