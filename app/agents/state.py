from typing import Optional, List, Dict, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from typing import Annotated


class ConversationState(TypedDict):
    # Conversation 
    messages: Annotated[list, add_messages]
    turn_count: int

    # Current parsed intent
    raw_query: str
    normalized_query: str

    retrieval_query: str
    brand: Optional[str]
    min_price: Optional[float]
    max_price: Optional[float]
    min_rating: Optional[float]
    attributes: List[str]
    semantic_constraints: List[str]

    # Brand intent flag 
    brand_was_explicit: bool

    # General chat 
    quick_response: Optional[str]  

    # Search / similar results 
    search_results: List[Dict]
    similar_products: List[Dict]

    # Detail view (set by details_node) 
    # Full structured dict for a single product. Cleared on new_search / refine.
    detail_product: Optional[Dict[str, Any]]

    # Comparison (set by compare_node) 
    # Shape: { fields, products, highlight }
    comparison: Optional[Dict[str, Any]]

    # Loop budget (evaluator-owned) 
    search_attempts: int
    relaxation_budget: int
    relaxation_log: List[str]
    drop_field: Optional[str]

    # Constraint history 
    constraint_history: List[Dict[str, Any]]

    # Clarification 
    needs_clarification: bool
    clarification_question: Optional[str]
    awaiting_user_response: bool
    pending_clarification_field: Optional[str]

    # Control flow 
    next_action: str

    # Structured JSON response (populated by runner, not nodes) 
    response_payload: Optional[Dict[str, Any]]

    # Session persistence (added for chat history) 
    conversation_history: List[Dict[str, Any]]  