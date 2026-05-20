"""
compare.py — Compare 2–3 products side-by-side.

Triggered when supervisor detects a compare intent.
Resolves product references from search_results (positional or name-based),
then writes structured comparison data into state["comparison"].
"""

import re
from app.agents.state import ConversationState
from app.retrieval.hybrid import HybridRetriever
from langchain_core.messages import HumanMessage, AIMessage

def _get_retriever() -> HybridRetriever:
    return HybridRetriever()


# ── Position word → 0-based index ─────────────────────────────────────────────
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

# Fields shown in the comparison table, in display order
COMPARE_FIELDS = [
    "title",
    "vendor",
    "price_range",
    "avg_rating",
    "total_reviews",
    "description",
    "variants_count",
    "image_url",
    "product_handle",
    "shopify_gid",
]


def compare_node(state: ConversationState) -> ConversationState:
    """
    1. Resolve which products the user wants to compare.
    2. Fetch full details for each.
    3. Build a structured comparison dict and store it in state.
    """
    results = state.get("search_results", [])
    if not results:
        return _append_message(
            state,
            "No products in context to compare. Try searching first.",
            response_type="error",
        )

    # Capture the user message to detect "all"
    messages = state.get("messages", [])
    latest_human = next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)),
        state.get("raw_query") or "",
    )
    
    handles = _resolve_compare_references(state, results)

    # If less than 2, fall back to first two
    if len(handles) < 2:
        handles = [
            r["product_handle"] 
            for r in results[:2]
            if r.get("product_handle")
        ]

    if len(handles) < 2:
        return _append_message(
            state,
            "I need at least two products to compare. Could you search for something first?",
            response_type="error",
        )

    # Cap at 5 products for comparison (avoid token/payload bloat)
    limit_message = None
    if len(handles) > 5:
        limit_message = f"I can only compare up to 5 products at once. Comparing the first 5."
        handles = handles[:5]
        print(f"[Compare] Limiting comparison to first 5 products")

    # Fetch full details
    products = []
    retriever = _get_retriever()

    for handle in handles:
        details = retriever.get_product_details(handle)
        if details:
            products.append(_slim_product(details))
        else:
            # Fall back to whatever we have in search_results
            fallback = next(
                (r for r in results if r.get("product_handle") == handle), 
                None
            )
            if fallback:
                products.append(_slim_from_result(fallback))

    if len(products) < 2:
        return _append_message(
            state,
            "I couldn't fetch enough product details to compare right now.",
            response_type="error",
        )

    comparison = _build_comparison_table(products)
    
    # Generate appropriate message based on count
    if limit_message:
        msg = limit_message
    elif "all" in latest_human.lower() or "both" in latest_human.lower():
        if len(products) == 5 and len(results) > 5:
            msg = f"Comparing the top 5 products (limit reached). Say 'compare 1,2,3' for specific ones."
        else:
            msg = f"Comparing all {len(products)} products for you."
    else:
        msg = f"Comparing {len(products)} products for you."

    return {
        **state,
        "comparison": comparison,
        "messages": state.get("messages", []) + [AIMessage(content=msg)],
    }


# ── Reference resolution ───────────────────────────────────────────────────────

# compare.py - replace the _resolve_compare_references function

def _resolve_compare_references(
    state: ConversationState, results: list
) -> list[str]:
    """
    Extract which products the user wants compared.

    Strategies (in order):
    1. "all" or "both" or "each" or numbers like "all 3"
    2. Positional words: "compare the first and third"
    3. Number extraction: "compare 1 and 3"
    4. Title-word fuzzy: "compare Nike and Adidas"
    5. Fallback: first two results
    """
    messages = state.get("messages", [])
    latest_human = next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)),
        state.get("raw_query") or "",
    )
    raw = latest_human.lower()

    if re.search(r'\ball\b|\bboth\b|\beach\b|\ball\s+(\d+)\b', raw):
        all_match = re.search(r'all\s+(\d+)', raw)
        if all_match:
            count = int(all_match.group(1))
            if count > 5:
                print(f"[Compare] User requested {count} products, limiting to 5")
            limit = min(count, len(results), 5)
        else:
            limit = min(len(results), 5)

        handles = []
        for i in range(limit):
            handle = results[i].get("product_handle")
            if handle:
                handles.append(handle)

        if len(handles) >= 2:
            if limit == 5 and len(results) > 5:
                print(f"[Compare] User requested 'all' → comparing {len(handles)} products (capped at 5)")
            else:
                print(f"[Compare] User requested 'all' → comparing {len(handles)} products")
            return handles

    handles: list[str] = []
    seen_indices: set[int] = set()

    # 1. Positional words
    for word, idx in _POSITION_MAP.items():
        if re.search(rf"\b{re.escape(word)}\b", raw) and idx < len(results):
            if idx not in seen_indices:
                handle = results[idx].get("product_handle")
                if handle:
                    handles.append(handle)
                seen_indices.add(idx)

    if len(handles) >= 2:
        return handles

    # 2. Bare numbers ("compare 1 and 3")
    for m in re.finditer(r"\b([1-9]|10)\b", raw):
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(results) and idx not in seen_indices:
            handle = results[idx].get("product_handle")
            if handle:
                handles.append(handle)
            seen_indices.add(idx)

    if len(handles) >= 2:
        return handles

    # 3. Title-word fuzzy match
    for result in results:
        title_words = [w for w in (result.get("title") or "").lower().split() if len(w) > 3]
        if any(w in raw for w in title_words):
            h = result.get("product_handle")
            if not h:
                continue
            if h not in handles:
                handles.append(h)

    # 4. Fallback: first two if we have nothing else
    if len(handles) < 2:
        handles = [
            r["product_handle"] 
            for r in results[:2]
            if r.get("product_handle")
        ]

    return handles


# ── Comparison table builder ───────────────────────────────────────────────────

def _build_comparison_table(products: list[dict]) -> dict:
    """
    Returns a structured comparison dict ready for JSON serialisation.

    Shape:
    {
        "fields": ["title", "vendor", ...],
        "products": [
            {"title": "...", "vendor": "...", ...},
            ...
        ],
        "highlight": {          # which product wins on each field
            "price":  0,        # index into products
            "rating": 1,
        }
    }
    """
    highlight: dict[str, int] = {}

    # Best price (lowest min_price) - only if at least 2 products have prices
    prices = [p.get("min_price") for p in products]
    valid_prices = [(v, i) for i, v in enumerate(prices) if v is not None]
    if len(valid_prices) >= 2:
        highlight["price"] = min(valid_prices, key=lambda x: x[0])[1]

    # Best rating (highest avg_rating) - only if at least 2 have ratings
    ratings = [p.get("avg_rating") for p in products]
    valid_ratings = [(v, i) for i, v in enumerate(ratings) if v is not None]
    if len(valid_ratings) >= 2:
        highlight["rating"] = max(valid_ratings, key=lambda x: x[0])[1]

    return {
        "fields": COMPARE_FIELDS,
        "products": products,
        "highlight": highlight,
    }

# ── Product shaping ────────────────────────────────────────────────────────────

def _slim_product(details: dict) -> dict:
    """Shape a full product-details dict into comparison-friendly form."""
    return {
        "product_handle":  details.get("product_handle"),
        "shopify_gid":     details.get("shopify_gid"),
        "title":           details.get("title"),
        "vendor":          details.get("vendor"),
        "price_range":     details.get("price_range"),
        "min_price":       details.get("min_price"),
        "avg_rating":      details.get("avg_rating"),
        "total_reviews":   details.get("total_reviews", 0),
        "description":     (details.get("description") or "")[:200],
        "variants_count":  len(details.get("variants") or []),
        "image_url":       details.get("image_url"),
    }


def _slim_from_result(r: dict) -> dict:
    """Shape a search-result dict (fewer fields) into comparison-friendly form."""
    return {
        "product_handle":  r.get("product_handle"),
        "shopify_gid":     r.get("shopify_gid"),
        "title":           r.get("title"),
        "vendor":          r.get("vendor"),
        "price_range":     None,
        "min_price":       r.get("min_price"),
        "avg_rating":      r.get("avg_rating"),
        "total_reviews":   r.get("review_count", 0),
        "description":     (r.get("description") or "")[:200],
        "variants_count":  None,
        "image_url":       r.get("image_url"),
    }


# ── Helper ─────────────────────────────────────────────────────────────────────

def _append_message(
    state: ConversationState, text: str, response_type: str = "message"
) -> ConversationState:
    return {
        **state,
        "messages": state.get("messages", []) + [AIMessage(content=text)],
    }