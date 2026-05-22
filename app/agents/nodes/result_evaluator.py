from app.agents.state import ConversationState
from app.logging import get_logger

logger = get_logger(__name__)

MIN_STABLE_RESULTS = 2
MAX_RESULTS = 10
INITIAL_RELAXATION_BUDGET = 3

# Relaxation priority
RELAXATION_ORDER = [
    "min_rating",
    "min_price",
    "attributes",
    "semantic_constraints",
    "max_price",
    "brand",
]

def result_evaluator_node(state: ConversationState) -> ConversationState:
    """
    Single brain for all loop control.
    Decides: respond | expand | clarify | no_results
    """
    results = state.get("search_results", [])
    budget = state.get("relaxation_budget", INITIAL_RELAXATION_BUDGET)
    attempts = state.get("search_attempts", 0)
    n = len(results)
    
    # Count how many active constraints exist
    active_constraints = _count_active_constraints(state)
    
    # If we've attempted relaxation and still have 0 results
    if n == 0 and attempts > 1 and budget <= 0:
        logger.info(f"No results after full relaxation -> no_results fallback")
        return {
            **state, 
            "next_action": "no_results", 
            "drop_field": None
        }
    
    # If all constraints are gone and still 0 results
    if n == 0 and active_constraints == 0 and attempts >= 2:
        print(f"[Evaluator] No constraints, still no results → no_results")
        return {
            **state, 
            "next_action": "no_results", 
            "drop_field": None
        }
    
    # Too many results → NEW: show top 5 rated products instead of clarifying 
    if n > MAX_RESULTS:
        logger.info(f"{n} results (too many) -> showing top 5 rated products")
        
        # Sort by rating and take top 5
        sorted_results = sorted(
            [r for r in results if r.get("avg_rating") is not None],
            key=lambda x: x.get("avg_rating", 0),
            reverse=True
        )
        
        # If no ratings, fall back to original order
        if not sorted_results:
            sorted_results = results[:5]
        else:
            sorted_results = sorted_results[:5]
        
        # Replace search_results with top rated only
        return {
            **state,
            "search_results": sorted_results,
            "next_action": "respond",  # Go straight to respond, no clarification
            "drop_field": None,
        }
    
    # Zero results = always expand/clarify 
    if n == 0:
        if budget <= 0:
            logger.info("Budget exhausted -> no_results fallback")
            return {
                **state, 
                "next_action": "no_results", 
                "drop_field": None
            }

        field = _pick_drop_field(state)
        if field is None:
            logger.info("Nothing left to relax -> no_results")
            return {
                **state, 
                "next_action": "no_results", 
                "drop_field": None
            }

        logger.info(f"0 results, budget = {budget} -> expand '{field}'")
        
        return {
            **state,
            "next_action": "expand",
            "drop_field": field,
            "relaxation_budget": budget - 1,
        }

    # 1 result with active constraints = expand

    if n == 1 and active_constraints > 0:
        if budget <= 0:
            logger.info(f"1 result but budget exhausted -> respond anyway")

            return {
                **state, 
                "next_action": "respond", 
                "drop_field": None
            }
        
        field = _pick_drop_field(state)
        if field:
            logger.info(f"1 result with {active_constraints} constraints -> expand '{field}'")
            return {
                **state,
                "next_action": "expand",
                "drop_field": field,
                "relaxation_budget": budget - 1,
            }

    # 2+ results = respond 
    logger.info(f"{n} results (active constraints: {active_constraints}) -> respond")
    return {
        **state, 
        "next_action": "respond", 
        "drop_field": None
    }

def _count_active_constraints(state: ConversationState) -> int:
    """Count how many non-default filters are active."""
    count = 0
    
    if state.get("brand") and state.get("brand_was_explicit", False):
        count += 1
    if state.get("min_price") is not None:
        count += 1
    if state.get("max_price") is not None:
        count += 1
    if state.get("min_rating") is not None:
        count += 1
    if state.get("attributes") and len(state.get("attributes", [])) > 0:
        count += 1
    
    return count


def _pick_drop_field(state: ConversationState) -> str | None:
    """Walk relaxation order and return the first droppable field."""
    brand_explicit = state.get("brand_was_explicit", False)
    candidates = []

    for field in RELAXATION_ORDER:
        val = state.get(field)
        has_value = val is not None and val != [] and val != ""
        if not has_value:
            continue
        if field == "brand" and brand_explicit:
            continue
        candidates.append(field)

    if candidates:
        return candidates[0]

    if state.get("brand") and brand_explicit:
        return "brand"

    return None


def route_after_evaluator(state: ConversationState) -> str:
    return state["next_action"]