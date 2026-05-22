import re
import httpx
from groq import Groq
from app.config import settings
from app.retrieval.hybrid import HybridRetriever
from app.agents.state import ConversationState
from langchain_core.messages import AIMessage, HumanMessage
from app.logging import get_logger

logger = get_logger(__name__)

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

def _get_retriever() -> HybridRetriever:
    return HybridRetriever()


# Position word / 0-based index 
_POSITION_MAP: dict[str, int] = {
    "first": 0, "1st": 0, "1": 0,
    "second": 1, "2nd": 1, "2": 1,
    "third": 2, "3rd": 2, "3": 2,
    "fourth": 3, "4th": 3, "4": 3,
    "fifth": 4, "5th": 4, "5": 4,
    "sixth": 5, "6th": 5, "6": 5,
    "seventh": 6, "7th": 6, "7": 6,
    "eighth": 7, "8th": 7, "8": 7,
    "ninth": 8, "9th": 8, "9": 8,
    "tenth": 9, "10th": 9, "10": 9,
}


# Product Details Node 
def details_node(state: ConversationState) -> ConversationState:
    """
    Resolve which product the user means, fetch full details,
    and store the structured dict in state["detail_product"].
    No prose generation — runner builds the JSON payload.
    """
    results = state.get("search_results", [])
    if not results:
        return _append_message(
            state,
            "I don't have any products in context. Try searching first.",
            clear_detail=True,
        )
    
    handle, resolved_index = _resolve_product_reference(state, results)

    if handle is None:
        if len(results) == 1:
            handle = results[0].get("product_handle")
            resolved_index = 0
        else:
            product_list = ", ".join([
                f"'{r.get('title', 'Product')}'" 
                for r in results[:3]
            ])

            return _append_message(
                state,
                f"Which product did you mean? I see: {product_list}. Please tell me the number (1, 2, 3) or name.",
                clear_detail=True,
            )

    details = _get_retriever().get_product_details(handle)
    if not details:
        return _append_message(
            state,
            "Sorry, I couldn't fetch details for that product.",
            clear_detail=True,
        )

    structured = _shape_details(details, resolved_index)

    # Minimal prose for accessibility / notification — frontend should use structured data
    title = details.get("title", "that product")
    text = f"Here are the details for {title}."

    return {
        **state,
        "detail_product": structured,
        "messages": state.get("messages", []) + [AIMessage(content=text)],
    }


def _shape_details(d: dict, index: int | None) -> dict:
    """Shape a full product-details dict into a structured frontend-ready payload."""
    variants = d.get("variants") or []
    reviews = d.get("reviews") or []

    top_review = None
    if reviews:
        r = reviews[0]
        top_review = {
            "body":          (r.get("body") or "")[:300],
            "reviewer_name": r.get("reviewer_name", "Anonymous"),
            "rating":        r.get("rating"),
        }

    return {
        "product_handle":    d.get("product_handle"),
        "shopify_gid":       d.get("shopify_gid"),
        "shopify_product_id":d.get("shopify_product_id"),
        "title":             d.get("title"),
        "vendor":            d.get("vendor"),
        "price_range":       d.get("price_range"),
        "min_price":         d.get("min_price"),
        "avg_rating":        d.get("avg_rating"),
        "total_reviews":     d.get("total_reviews", 0),
        "description":       d.get("description"),
        "image_url":         d.get("image_url"),
        "category":          d.get("category"),
        "variants_count":    len(variants),
        "variants":          variants[:10],   # cap to avoid payload bloat
        "top_review":        top_review,
        "resolved_index":    index,           # which list position was selected (0-based)
    }


def similar_node(state: ConversationState) -> ConversationState:
    """
    1. Resolve WHICH product the user wants similar items for
       (positional word, bare number, or title-word fuzzy — NOT always index 0).
    2. Fetch similar products.
    3. Store them in search_results (so positional refs work next turn).
    No prose — runner builds the JSON payload.
    """
    results = state.get("search_results", [])
    if not results:
        return _append_message(
            state,
            "No product in context to find similar ones for. Try a search first.",
        )

    handle, resolved_index = _resolve_product_reference(state, results)

    # Only fall back to index 0 if nothing resolved AND there's no ambiguity signal
    if handle is None:
        if len(results) == 1:
            handle = results[0].get("product_handle")
            resolved_index = 0
        else:
            product_list = ", ".join([
                f"'{r.get('title', 'Product')}'" 
                for r in results[:3]
            ])
            
            return _append_message(
                state,
                f"Which product do you want similar items for? I see: {product_list}. Please tell me the number (1, 2, 3) or name.",
            )

    source = next(
        (r for r in results if r.get("product_handle") == handle),
        results[resolved_index if resolved_index is not None else 0],
    )
    source_title = source.get("title", "that item")

    similar_raw = _get_retriever().get_similar_products(product_handle=handle, limit=6)
    
    if not similar_raw:
        return _append_message(state, f"I couldn't find products similar to {source_title}")

    normalised = _normalise_similar(similar_raw)

    text = f"Products similar to {source_title}."

    return {
        **state,
        "search_results":   normalised,
        "similar_products": normalised,
        "messages": state.get("messages", []) + [AIMessage(content=text)],
    }


def _normalise_similar(similar: list) -> list:
    """Pad slim RPC results to match search_results shape."""
    return [
        {
            "product_handle":    p.get("product_handle"),
            "shopify_gid":       p.get("shopify_gid"),
            "shopify_product_id":p.get("shopify_product_id"),
            "title":             p.get("title"),
            "vendor":            p.get("vendor"),
            "min_price":         p.get("min_price"),
            "image_url":         p.get("image_url"),
            "category":          p.get("category"),
            "avg_rating":        p.get("avg_rating"),      # include if RPC returns it
            "review_count":      p.get("review_count", 0),
            "reviews":           [],
            "score":             0,
        }
        for p in similar
    ]

def _resolve_product_reference(
    state: ConversationState,
    results: list,
) -> tuple[str | None, int | None]:
    """
    Return (product_handle, 0-based-index) for the product the user is referring to.
    Returns (None, None) if nothing can be resolved.

    Resolution order:
    1. Positional words  — "the third one", "2nd"
    2. Bare numbers      — "tell me about 3"
    3. Title-word fuzzy  — any meaningful word from a product title found in the message
    """
    messages = state.get("messages", [])
    latest_human = next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)),
        state.get("raw_query") or "",
    )
    raw = latest_human.lower()

    # 1. Positional words
    for word, idx in _POSITION_MAP.items():
        if re.search(rf"\b{re.escape(word)}\b", raw) and idx < len(results):
            handle = results[idx].get("product_handle")
            if handle:
                return handle, idx

    # 2. Bare numbers ("tell me about 3" / "details for 2")
    for m in re.finditer(r"\b([1-9]|10)\b", raw):
        idx = int(m.group(1)) - 1
        
        if 0 <= idx < len(results):  # ← This already guards out-of-range
            handle = results[idx].get("product_handle")
            if handle:
                return handle, idx
        else:
            # Optional: log that user referenced beyond available results
            logger.info(f"[Reference] User requested index {idx+1} but only {len(results)} available")


    # 3. Title-word fuzzy (skip very short / common words)
    _STOPWORDS = {
        "the", "and", "for", "with", "this", "that", "from", "show", "tell", 
        "more", "about"
    }
    
    for i, r in enumerate(results):
        title_words = [
            w for w in (r.get("title") or "").lower().split()
            if len(w) > 3 and w not in _STOPWORDS
        ]
    
        if any(w in raw for w in title_words):
            handle = r.get("product_handle")
            if handle:
                return handle, i

    return None, None

def general_respond_node(state: ConversationState) -> ConversationState:
    """Handle non-search messages like greetings, thanks, general questions."""
    
    # Check if supervisor gave a quick response (bypass LLM)
    if state.get("quick_response"):
        text = state["quick_response"]

        # Remove temp field so it doesn't persist
        state = {
            k: v 
            for k, v in state.items() 
            if k != "quick_response"
        }
        
        return {
            **state,
            "messages": state.get("messages", []) + [AIMessage(content=text)],
        }
    
    # Otherwise use LLM for general chat
    messages = state.get("messages", [])
    last_user_msg = messages[-1].content if messages else ""

    try:
        response = _get_client().chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful shopping assistant. "
                        "Keep responses VERY short (1 sentence max). "
                        "Be friendly and conversational."
                    ),
                },
                {"role": "user", "content": last_user_msg},
            ],
            temperature=0.6,
            max_tokens=50,
        )
        text = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM error: {e}")
        text = "How can I help you find something today?"

    return _append_message(state, text)

def _append_message(
    state: ConversationState,
    text: str,
    clear_detail: bool = False,
) -> ConversationState:
    updates: dict = {
        "messages": state.get("messages", []) + [AIMessage(content=text)],
    }

    if clear_detail:
        updates["detail_product"] = None

    return {
        **state, 
        **updates
    }