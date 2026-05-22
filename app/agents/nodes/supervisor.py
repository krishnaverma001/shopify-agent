import re
import json
import httpx
from groq import Groq
from app.config import settings
from app.agents.state import ConversationState
from app.logging import get_logger

logger = get_logger(__name__)

from app.retrieval.hybrid import HybridRetriever
retriever = HybridRetriever()

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



SYSTEM_PROMPT = """You are a supervisor for a shopping assistant.
Classify what the user wants based on the conversation history.

Return ONLY valid JSON:
{
  "action": "<one of the actions below>",
  "reason": "<one sentence>"
}

Actions:
- "new_search"  : user is asking for a completely new product (no prior results, or completely different product)
- "refine"      : user wants to change or add constraints to current results (cheaper, better rating, specific brand, etc.)
- "details"     : user wants more info about a specific product from the currently visible list
- "similar"     : user wants products similar to one in the currently visible list
- "compare"     : user wants to compare 2-3 products from the currently visible list side-by-side (includes "compare all", "compare both", "compare each", "compare 1 2 3")
- "respond"     : user is chatting, greeting, saying thanks, or asking a non-product question
- "reset"       : user wants to abandon current search (says: leave it, forget it, never mind, cancel, stop, ignore)

Rules:
- NEVER output "expand" or "clarify" — those are handled elsewhere
- If there are NO previous results, any product query is "new_search"
- If there ARE previous results and user adds OR removes constraints → "refine"
- Positional references ("the first one", "the third one", "that one") against the VISIBLE LIST → "details", "similar", or "compare"
- "compare" triggers on: "compare", "vs", "versus", "difference between", "which is better", "side by side", "side-by-side", "compare all", "compare both", "compare each"
- The visible list may be search results OR similar products shown in the last assistant message
- When in doubt between new_search and refine → prefer "refine" if results exist
"""

def supervisor_node(state: ConversationState) -> ConversationState:
    """Classify entry intent only. Never routes expand or clarify."""

    # Reset/cancel detection (HIGHEST priority) 
    latest_message = state.get("messages", [])[-1].content if state.get("messages") else ""
    msg_lower = latest_message.lower().strip()

    logger.info(f"Processing message: '{latest_message[:100]}'")

    # Only trigger on EXACT phrases that mean abandon the search
    reset_phrases = [
        "forget it",
        "forget that", 
        "never mind",  # keep this but with boundary check
        "cancel",
        "stop",
        "ignore that",
        "scratch that",
        "start over",
        "reset search",
        "clear search"
    ]
    
    # Check for EXACT phrase or phrase with punctuation only
    is_reset = False
    for phrase in reset_phrases:
        # Match phrase as whole word sequence
        pattern = r'\b' + r'\s+'.join(re.escape(word) for word in phrase.split()) + r'\b'
        if re.search(pattern, msg_lower):
            is_reset = True
            break
    
    false_positive_patterns = [
        r"don't\s+worry\s+about",      # "don't worry about X"
        r"never\s+mind\s+the\s+",      # "never mind the price/brand/color"
        r"never\s+mind\s+that\s+",      # "never mind that constraint"
        r"forget\s+about\s+the\s+",     # "forget about the budget"
        r"ignore\s+the\s+",              # "ignore the previous filter"
        r"skip\s+that\s+(?:one|item|product)",  # "skip that product"
        r"just\s+stop\s+showing\s+",     # "stop showing expensive ones"
        r"cancel\s+the\s+(?:filter|constraint)",  # "cancel the filter"
    ]

    # If any false positive pattern matches, NOT a reset
    for pattern in false_positive_patterns:
        if re.search(pattern, msg_lower):
            logger.info(f"False positive prevented: pattern '{pattern}' matched")
            is_reset = False
            break
    
    if is_reset:
        logger.info(f"Reset detected: '{latest_message}'")
        return {
            **state,
            "next_action": "reset",
            "awaiting_user_response": False,
            "needs_clarification": False,
            "clarification_question": None,
            "pending_clarification_field": None,
        }

    # Quick general chat detection (bypass LLM) 
    quick_chat_keywords = {
        "hi": "Hello! What can I help you find today?",
        "hello": "Hi there! Looking for something specific?",
        "hey": "Hey! Ready to shop?",
        "thanks": "You're welcome! Anything else I can help with?",
        "thank you": "My pleasure! What else are you looking for?",
        "bye": "Goodbye! Come back anytime.",
        "goodbye": "See you later! Happy shopping!",
        "who are you": "I'm your AI shopping assistant. I can help find products, compare items, and answer questions. What would you like to look for?",
        "what can you do": "I can search for products, show details, find similar items, and compare products. Just tell me what you're interested in!",
        "help": "I can help you search for products, compare items, or answer questions. What are you looking for today?",
        "joke": "Why did the laptop go to therapy? It had too many tabs open! 😊 Want to search for something?",
    }
    
    if msg_lower in quick_chat_keywords:
        logger.info(f"Quick chat exact match for '{msg_lower}'")
        return {
            **state,
            "next_action": "respond",
            "quick_response": quick_chat_keywords[msg_lower],
        }
        
    # Fast-path: answering a clarifying question 
    if state.get("awaiting_user_response"):
        logger.info("Calling Refine (answering clarification)")
        
        # NEW: Apply the clarification answer as a filter
        user_response = state.get("messages", [])[-1].content if state.get("messages") else ""
        pending_field = state.get("pending_clarification_field")
        
        updated_state = {**state}
        
        if pending_field == "price" and user_response:
            # Try to extract price value
            
            price_match = re.search(r'\$?(\d+(?:\.\d+)?)', user_response)
            if price_match:
                price = float(price_match.group(1))
                updated_state["max_price"] = price
                
                logger.info(f"Applied price filter: ≤ ${price}")
            
            elif "under" in user_response.lower() or "less than" in user_response.lower():
                price_match = re.search(r'(\d+(?:\.\d+)?)', user_response)
                if price_match:
                    price = float(price_match.group(1))
                    updated_state["max_price"] = price
                    logger.info(f"Applied price filter: ≤ ${price}")
        
        elif pending_field == "brand" and user_response:
            updated_state["brand"] = user_response.strip()
            updated_state["brand_was_explicit"] = True
            logger.info(f"Applied brand filter: {user_response}")
        
        elif pending_field == "rating" and user_response:
            
            rating_match = re.search(r'(\d+(?:\.\d+)?)', user_response)
            if rating_match:
                rating = float(rating_match.group(1))
                updated_state["min_rating"] = rating
                logger.info(f"Applied rating filter: ≥ {rating}")
        
        # Reset clarification flags
        return {
            **updated_state,
            "next_action": "refine",
            "awaiting_user_response": False,
            "needs_clarification": False,
            "relaxation_budget": 3,
            "clarification_question": None,
            "pending_clarification_field": None,
        }

    has_results = bool(state.get("search_results"))
    latest_message = state.get("messages", [])[-1].content if state.get("messages") else ""

    if has_results:
        is_pos_ref, pos_action = _is_positional_reference(latest_message)
        if is_pos_ref:
            logger.info(f"Positional reference detected -> {pos_action} (bypassing LLM)")
            return {
                **state,
                "next_action": pos_action,
            }
    
    # Then topic change check
    if has_results and _is_topic_change(state, latest_message):
        logger.info("Topic change detected -> forcing new_search")
        return {
            **state,
            "next_action": "new_search",
            "comparison": None,
            "detail_product": None,
        }
    
    current_filters = {
        "brand": state.get("brand"),
        "min_price": state.get("min_price"),
        "max_price": state.get("max_price"),
        "min_rating": state.get("min_rating"),
        "query": state.get("retrieval_query"),
    }

    visible_list = _build_visible_list(state)

    recent_messages = state.get("messages", [])[-3:]
    history_text = "\n".join(
        f"{m.type.upper()}: {m.content}" for m in recent_messages
    )

    user_prompt = f"""Conversation so far:
{history_text}

Current search context:
- Has existing results: {has_results}
- Active filters: {json.dumps(current_filters)}
- Currently visible products (what the user can see and refer to):
{visible_list}

Classify the latest user message"""

    
    logger.info(f"Sending to LLM for classification")

    try:
        response = _get_client().chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system", 
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user", 
                    "content": user_prompt
                },
            ],
            temperature=0.0,
            max_tokens=100,
        )
        result = json.loads(response.choices[0].message.content)
        action = result.get("action", "new_search")

        # Hard guard — supervisor must never emit these
        if action in ("expand", "clarify"):
            logger.info(f"Blocked illegal action '{action}' → defaulting")
            action = "refine" if has_results else "new_search"

    except Exception as e:
        logger.error(f"LLM error: {e}, defaulting to new_search")
        action = "new_search"

    # Only clear stale data if it's a true new search/refine (not a positional reference)
    clear_stale = action in ("new_search", "refine") 

    return {
        **state,
        "next_action": action,
        **({"comparison": None, "detail_product": None} if clear_stale else {}),
    }


def _build_visible_list(state: ConversationState) -> str:
    """Builds list of product details from state"""
    
    results = state.get("search_results", [])
    if not results:
        return "  (none)"
    lines = []
    for i, r in enumerate(results[:6], 1):
        price = f"${r['min_price']:.2f}" if r.get("min_price") else "N/A"
        lines.append(f"  {i}. {r.get('title', 'Unknown')} — {price}")
    return "\n".join(lines)

def _is_positional_reference(msg: str) -> tuple:
    """Returns (is_positional, suggested_action)"""
    msg_lower = msg.lower()

    if any(word in msg_lower for word in ["compare", "vs", "versus", "difference", "side by side"]):
        return True, "compare"
    
    position_patterns = [
        r"\bfirst\b", r"\b1st\b", r"\b#1\b", r"\b1\b",  
        r"\bsecond\b", r"\b2nd\b", r"\b#2\b", r"\b2\b", 
        r"\bthird\b", r"\b3rd\b", r"\b#3\b", r"\b3\b",
        r"\bfourth\b", r"\b4th\b", r"\b#4\b", r"\b4\b",
        r"\bfifth\b", r"\b5th\b", r"\b#5\b", r"\b5\b",
        r"\bthat one\b", r"\bthis one\b",
        r"\bthe (\w+) one\b"
    ]
    
    if any(re.search(p, msg_lower) for p in position_patterns):
        # Determine which action
        if any(word in msg_lower for word in ["details", "info", "tell me about", "more about", "about"]):
            return True, "details"
        elif any(word in msg_lower for word in ["similar", "like this", "more like", "find more like"]):
            return True, "similar"
        elif any(word in msg_lower for word in ["compare", "vs", "versus", "difference"]):
            return True, "compare"
        else:
            # Default to details for bare "first one", "that one"
            return True, "details"
    
    return False, None
    
# def _is_topic_change(state: ConversationState, user_message: str) -> bool:
#     """Detect if user is asking about a completely different product category."""
    
#     old_query = state.get("retrieval_query", "")
#     if not old_query:
#         return False

    
#     msg = user_message.lower().strip()

#     # Never flag topic change on short replies (clarification answers like "yes", "sure", "no")
#     if len(msg.split()) <= 4:
#         return False

#     # Never flag when message contains similarity/detail/comparison intent words
#     context_ref_patterns = [
#         r"\bfirst\b", r"\b1st\b", r"\b#?1\b",
#         r"\bsecond\b", r"\b2nd\b", r"\b#?2\b",
#         r"\bthird\b", r"\b3rd\b", r"\b#?3\b",
#         r"\bfourth\b", r"\b4th\b", r"\b#?4\b",
#         r"\bfifth\b", r"\b5th\b", r"\b#?5\b",
#         r"\bthat one\b", r"\bthis one\b", r"\bthis\b", r"\bit\b",
#         r"\bdetails\b", r"\binfo\b", r"\binformation\b",
#         r"\bsimilar\b", r"\blike this\b", r"\blike it\b", r"\blike that\b",
#         r"\bcompare\b", r"\bvs\b", r"\bversus\b",
#     ]
#     for pattern in context_ref_patterns:
#         if re.search(pattern, msg):
#             print(f"[TopicChange] Context reference detected → NOT a topic change")
#             return False

#     # Explicit reset signals only
#     new_search_indicators = [
#         "actually", "instead", "forget that", "never mind",
#         "what about", "looking for", "need a", "search for",
#     ]
#     if any(indicator in msg for indicator in new_search_indicators):
#         return True

#     # Word overlap check — only fire if queries are both substantive AND share nothing
#     STOPWORDS = {"a", "an", "the", "for", "with", "any", "some", "are", "is",
#                  "to", "of", "in", "on", "and", "or", "me", "my", "i", "can",
#                  "you", "show", "find", "get", "want", "do", "have"}
#     old_words = set(old_query.lower().split()) - STOPWORDS
#     new_words = set(msg.split()) - STOPWORDS

#     if not old_words or not new_words:
#         return False

#     if not old_words.intersection(new_words) and len(old_words) > 2 and len(new_words) > 2:
#         return True

#     return False

def _is_topic_change(state: ConversationState, user_message: str) -> bool:
    """Detect topic change using embedding similarity from HybridRetriever."""
    
    old_query = state.get("retrieval_query", "")
    if not old_query:
        return False
    
    # Short messages are refinements, not topic changes
    if len(user_message.split()) <= 4:
        return False
    
    # Refinement keywords - definitely not topic change
    refinement_keywords = ['cheaper', 'expensive', 'better', 'worse', 'higher', 'lower', 
                          'under', 'over', 'less than', 'more than', 'rating', 'brand',
                          'cheap', 'affordable', 'premium', 'budget', 'filter']
    if any(kw in user_message.lower() for kw in refinement_keywords):
        return False
    
    embedder = retriever.embedder
    
    # Compute embeddings on demand (no caching to state)
    old_embedding = embedder.encode([old_query])[0]
    new_embedding = embedder.encode([user_message])[0]
    
    # Calculate cosine similarity
    import numpy as np
    similarity = float(np.dot(old_embedding, new_embedding) / 
                      (np.linalg.norm(old_embedding) * np.linalg.norm(new_embedding)))
    
    logger.info(f"Similarity = {similarity:.3f} | '{old_query}' → '{user_message[:50]}'")
    
    # Decision thresholds
    if similarity >= 0.65:
        return False  # Same topic
    elif similarity < 0.45:
        return True   # Topic change
    else:
        return False  # Ambiguous - let LLM decide
    
def route_after_supervisor(state: ConversationState) -> str:
    return state["next_action"]