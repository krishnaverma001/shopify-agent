from typing import Any, Dict, Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    type: str   # "products" | "comparison" | "clarification" | "detail" | "similar" | "message" | "error"
    text: str
    meta: Dict[str, Any]

    products: Optional[list] = None
    comparison: Optional[Dict] = None
    clarification: Optional[Dict] = None
    detail: Optional[Dict] = None
    filters_applied: Optional[Dict] = None
    relaxations: Optional[list] = None