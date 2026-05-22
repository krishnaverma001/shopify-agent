import json
import httpx
from groq import Groq
from app.config import settings
from app.agents.state import ConversationState
from langchain_core.messages import AIMessage
from app.logging import get_logger

logger = get_logger(__name__)

_CLIENT = None
_HTTP_CLIENT = None

def _get_client() -> Groq:
    global _CLIENT, _HTTP_CLIENT
    if _CLIENT is None:
        # Create persistent HTTP client with connection pooling
        _HTTP_CLIENT = httpx.Client(
            limits=httpx.Limits(
                max_keepalive_connections=5,  
                max_connections=10,
                keepalive_expiry=30.0
            ),
            timeout=30.0,
            http2=True,  
            follow_redirects=True
        )
        _CLIENT = Groq(
            api_key=settings.GROQ_API_KEY,
            http_client=_HTTP_CLIENT
        )

    return _CLIENT

SYSTEM_PROMPT = """You are a friendly shopping assistant.
The search returned no results or the user's query is unclear.
Ask ONE short, specific clarifying question to help narrow down what they want.

Context you'll receive:
- What was searched for
- What filters were active
- How many relaxation attempts happened
- Whether results were zero or too many

Rules:
- One question only. No bullet lists.
- Be conversational, not robotic.
- If zero results after relaxing brand → ask if they're open to other brands.
- If zero results after relaxing price → ask for their actual budget.
- If too many results → ask which feature matters most.
- Keep it under 25 words.

Return ONLY the question string, no JSON, no preamble."""

def clarifier_node(state: ConversationState) -> ConversationState:
    """Generate a clarifying question and pause for user response."""
    
    client = _get_client()

    results = state.get("search_results", [])
    relaxation_log = state.get("relaxation_log", [])
    attempts = state.get("search_attempts", 0)

    context = {
        "original_query": state.get("raw_query"),
        "active_filters": {
            "brand": state.get("brand"),
            "max_price": state.get("max_price"),
            "min_price": state.get("min_price"),
            "min_rating": state.get("min_rating"),
        },
        "result_count": len(results),
        "relaxations_done": relaxation_log,
        "search_attempts": attempts,
        "situation": "zero results" if len(results) == 0 else "too many results",
    }

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(context)},
            ],
            temperature=0.4,
            max_tokens=80,
        )
        question = response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"LLM error: {e}")
        question = "Could you tell me a bit more about what you're looking for?"

    logger.info(f"Question: {question}")

    # Store this so when user responds, we know which filter to apply
    clarifying_feature = None
    question_lower = question.lower()

    if any(
        word in question_lower 
        for word in ["price", "budget", "cost", "dollar", "$"]
    ):
        clarifying_feature = "price"
    
    elif any(
        word in question_lower 
        for word in ["brand", "maker", "company", "manufacturer"]
    ):
        clarifying_feature = "brand"
    
    elif any(
        word in question_lower 
        for word in ["rating", "review", "star", "score"]
    ):
        clarifying_feature = "rating"
    
    elif any(
        word in question_lower 
        for word in ["type", "category", "kind", "style"]
    ):
        clarifying_feature = "category"

    return {
        **state,
        "messages": state.get("messages", []) + [AIMessage(content=question)],
        "needs_clarification": True,
        "clarification_question": question,
        "awaiting_user_response": True,
        "next_action": "clarify",
        "pending_clarification_field": clarifying_feature,
    }