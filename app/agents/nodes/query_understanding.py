from app.understanding.normalizer import QueryNormalizer
from app.understanding.parser import LLMQueryParser
from app.understanding.validator import QueryValidator
from app.understanding.models import ParsedQuery
from app.cache.brand_catalog import KNOWN_BRANDS
from app.config import settings
from app.agents.state import ConversationState

_normalizer = None
_parser = None
_validator = None

INITIAL_RELAXATION_BUDGET = 3


def _init():
    global _normalizer, _parser, _validator
    if _normalizer is None:
        _normalizer = QueryNormalizer()
        _parser = LLMQueryParser(api_key=settings.GROQ_API_KEY)
        _validator = QueryValidator(known_brands=KNOWN_BRANDS)


def _build_vector_query(parsed: ParsedQuery) -> str:
    parts = [
        parsed.retrieval_query,
        *parsed.attributes,
        *parsed.semantic_constraints,
    ]
    return " ".join([p for p in parts if p]).strip()


def query_understanding_node(state: ConversationState) -> ConversationState:
    _init()

    action = state.get("next_action", "new_search")
    messages = state.get("messages", [])
    raw_query = messages[-1].content if messages else state.get("raw_query", "")

    normalized = _normalizer.normalize(raw_query)
    extracted = _parser.parse(query=normalized)

    base = ParsedQuery(raw_query=raw_query, normalized_query=normalized)
    parsed = _validator.validate(base, extracted)

    # Detect if brand was explicitly named by the user
    brand_was_explicit = parsed.brand is not None

    if action == "new_search":
        history = state.get("constraint_history", [])
        snapshot = _current_constraints(state)
        if any(v is not None for v in snapshot.values()):
            history = history + [snapshot]

        return {
            **state,
            "raw_query": raw_query,
            "normalized_query": normalized,
            "retrieval_query": _build_vector_query(parsed),
            "brand": parsed.brand,
            "brand_was_explicit": brand_was_explicit,
            "min_price": parsed.min_price,
            "max_price": parsed.max_price,
            "min_rating": parsed.min_rating,
            "attributes": parsed.attributes,
            "semantic_constraints": parsed.semantic_constraints,
            "search_attempts": 0,
            "relaxation_budget": INITIAL_RELAXATION_BUDGET,
            "relaxation_log": [],
            "drop_field": None,
            "constraint_history": history,
        }

    elif action == "refine":
        # Merge new constraints — if user names a brand in a refine, mark explicit
        merged = _merge_constraints(state, parsed)
        new_explicit = state.get("brand_was_explicit", False) or brand_was_explicit
        return {
            **state,
            **merged,
            "raw_query": raw_query,
            "brand_was_explicit": new_explicit,
            # "search_attempts": 0,
            # "relaxation_budget": INITIAL_RELAXATION_BUDGET,
            # "relaxation_log": [],
            "drop_field": None,
        }

    # details / similar / respond — don't touch filters
    return {**state, "raw_query": raw_query}


def _current_constraints(state: ConversationState) -> dict:
    return {
        "retrieval_query": state.get("retrieval_query"),
        "brand": state.get("brand"),
        "min_price": state.get("min_price"),
        "max_price": state.get("max_price"),
        "min_rating": state.get("min_rating"),
        "attributes": state.get("attributes", []),
        "semantic_constraints": state.get("semantic_constraints", []),
    }


def _merge_constraints(state: ConversationState, parsed: ParsedQuery) -> dict:
    """Overlay only non-None values from new parse onto existing filters."""
    return {
        "retrieval_query": state.get("retrieval_query") or parsed.retrieval_query,
        "brand": parsed.brand or state.get("brand"),
        "min_price": parsed.min_price if parsed.min_price is not None else state.get("min_price"),
        "max_price": parsed.max_price if parsed.max_price is not None else state.get("max_price"),
        "min_rating": parsed.min_rating if parsed.min_rating is not None else state.get("min_rating"),
        "attributes": list(set(state.get("attributes", []) + parsed.attributes)),
        "semantic_constraints": list(set(state.get("semantic_constraints", []) + parsed.semantic_constraints)),
    }