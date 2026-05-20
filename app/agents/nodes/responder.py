import json
import httpx
from groq import Groq
from app.config import settings
from app.agents.state import ConversationState
from langchain_core.messages import AIMessage

_CLIENT = None
_HTTP_CLIENT = None

def _get_client() -> Groq:
    global _CLIENT, _HTTP_CLIENT
    if _CLIENT is None:
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

SYSTEM_PROMPT = """You are a helpful Shopify store assistant.
Present search results conversationally. Be concise and helpful.

Rules:
- Lead with a one-line summary of what you found.
- If there were too many results and we picked top-rated products, say so: "I found many Marvel items, so here are the top 5 highest-rated:"
- List each product: name, price, rating (if available), and one-line reason why it fits.
- If any filters were relaxed to find results, mention it naturally (e.g. "I couldn't find any under $50 so I widened to $75").
- End with ONE soft follow-up (e.g. "Want me to narrow this down?" or "Shall I show similar options?").
- Keep the whole response under 200 words.
- Use plain text. No markdown headers. Minimal bullet use.

Return only the response text."""

def responder_node(state: ConversationState) -> ConversationState:
    """Format search results into a natural assistant message."""

    results = state.get("search_results", [])
    relaxation_log = state.get("relaxation_log", [])
    raw_query = state.get("raw_query", "")

    # Slim down results for the prompt (avoid token bloat)
    slim_results = [
        {
            "title": r.get("title"),
            "price": r.get("min_price"),
            "rating": r.get("avg_rating"),
            "review_count": r.get("review_count", 0),
            "vendor": r.get("vendor"),
            "description": (r.get("description") or "")[:120],
        }
        for r in results[:5]
    ]

    payload = {
        "user_query": raw_query,
        "results": slim_results,
        "relaxations_applied": relaxation_log,
        "result_count": len(results),
    }

    try:
        response = _get_client().chat.completions.create(
            model="llama-3.3-70b-versatile",   # better for natural language
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload)},
            ],
            temperature=0.5,
            max_tokens=350,
        )
        text = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[Responder] LLM error: {e}")
        text = _fallback_response(results, relaxation_log)

    print(f"[Responder] Generated response ({len(text)} chars)")

    return {
        **state,
        "messages": state.get("messages", []) + [AIMessage(content=text)],
        "needs_clarification": False,
        "clarification_question": None,
        "awaiting_user_response": False,
    }


# responder.py - ADD to _fallback_response
def _fallback_response(results: list, relaxation_log: list) -> str:
    if not results:
        return "I couldn't find any matching products. Could you try a different search?"
    
    # ADD: Guard for missing min_price
    lines = []
    if relaxation_log:
        lines.append(f"Note: {relaxation_log[-1]}.")
    lines.append(f"Here are {len(results)} product(s) I found:")
    for r in results[:5]:
        # FIX: Handle missing min_price key
        price = f"${r.get('min_price', 0):.2f}" if r.get('min_price') else "N/A"
        rating = f" | ⭐{r.get('avg_rating', 0)}" if r.get('avg_rating') else ""
        lines.append(f"• {r.get('title', 'Unknown')} — {price}{rating}")
    return "\n".join(lines)

# responder.py - add this new function

def no_results_node(state: ConversationState) -> ConversationState:
    """Handle case when no products exist for the user's search."""
    
    raw_query = state.get("raw_query", "")
    relaxation_log = state.get("relaxation_log", [])
    
    # Create a helpful fallback message
    text = f"I couldn't find any products matching '{raw_query}' in our catalog. "
    text += "Would you like to try a different search?\n"

    # Reset state to allow new searches
    return {
        **state,
        "messages": state.get("messages", []) + [AIMessage(content=text)],
        "needs_clarification": False,
        "clarification_question": None,
        "awaiting_user_response": False,
        "next_action": "no_results",
        
        "brand": None,
        "min_price": None,
        "max_price": None,
        "min_rating": None,
        "attributes": [],
        "semantic_constraints": [],
        "search_results": [],
        "search_attempts": 0,
        "relaxation_budget": 3,
        "relaxation_log": [],
    }