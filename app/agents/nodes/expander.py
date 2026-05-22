from app.agents.state import ConversationState
from app.logging import get_logger

logger = get_logger(__name__)

# Price bump steps before dropping max_price entirely
PRICE_BUMP_PCTS = [0.25, 0.50]  # 25% then 50%


def expander_node(state: ConversationState) -> ConversationState:
    """
    Fully dumb executor — reads drop_field set by evaluator and acts on it.
    No logic of its own. No relaxation decisions.
    """
    
    field = state.get("drop_field")
    relaxation_log = list(state.get("relaxation_log", []))
    
    # Track original constraints for better messaging
    original_constraints = state.get("original_constraints", {})
    
    if not field:
        logger.info("No drop_field set — nothing to do")
        return state

    current_val = state.get(field)

    # Special case: max_price gets stepped up before being dropped
    if field == "max_price" and current_val is not None:
        # Count how many price expansions we've done in THIS search session
        
        price_expansions = sum(
            1 for e in relaxation_log 
            if e.startswith("Expanded budget") or e.startswith("Expanded your maximum budget")
        )
        
        # Store original user budget if not already saved
        
        if "original_max_price" not in original_constraints:
            original_constraints["original_max_price"] = current_val
        
        original_budget = original_constraints.get("original_max_price", current_val)
        
        if price_expansions < len(PRICE_BUMP_PCTS):
            pct = PRICE_BUMP_PCTS[price_expansions]
            new_max = round(original_budget * (1 + pct), 2)
            
            # User-friendly message with emoji for visibility
        
            if price_expansions == 0:
                msg = f"Expanded your budget from ${original_budget:.0f} to ${new_max:.0f} to find more options"
            else:
                msg = f"Further expanded budget to ${new_max:.0f} (originally ${original_budget:.0f})"
            
            relaxation_log.append(msg)
            logger.info(f"Expander Message: {msg}")
            
            return {
                **state, 
                "max_price": new_max, 
                "relaxation_log": relaxation_log, 
                "drop_field": None,
                "original_constraints": original_constraints,
            }

        # All bumps done — drop it
        msg = f"Removed price limit entirely (was ${original_budget:.2f}) - showing all prices"
        relaxation_log.append(msg)

        logger.info("Dropping max_price")
        
        return {
            **state, 
            "max_price": None, 
            "relaxation_log": relaxation_log, 
            "drop_field": None,
            "original_constraints": original_constraints,
        }

    # Special case: min_price gets dropped (always immediate drop, no stepping)
    if field == "min_price" and current_val is not None:
        msg = f"Removed minimum price requirement (was ${current_val:.0f}+) to show more products"
        relaxation_log.append(msg)
        logger.info(f"Expander message: {msg}")

        return {
            **state, 
            "min_price": None, 
            "relaxation_log": relaxation_log, 
            "drop_field": None,
        }

    # All other fields: drop to None / empty
    new_val = [] if field in ("attributes", "semantic_constraints") else None
    msg = _log_message(field, current_val)
    relaxation_log.append(msg)
    print(f"[Expander] {msg}")

    return {
        **state, 
        field: new_val, 
        "relaxation_log": relaxation_log, 
        "drop_field": None,
    }

def _log_message(field: str, value) -> str:
    """Safely format log message for any value type with user-friendly formatting."""
    
    # Handle None values
    if value is None:
        return f"Removed {field} filter"
    
    # Handle different field types with emojis for visual distinction
    if field == "min_rating":
        try:
            return f"Removed minimum rating filter (was ≥ {float(value):.1f} stars)"
        except (TypeError, ValueError):
            return f"Removed minimum rating filter (was {value})"
    
    elif field == "min_price":
        try:
            return f"Removed minimum price (was ${float(value):.0f}+) to find more matches"
        except (TypeError, ValueError):
            return f"Removed minimum price filter (was {value})"
    
    elif field == "max_price":
        try:
            return f"Removed price limit (was ≤${float(value):.0f}) - now showing all prices"
        except (TypeError, ValueError):
            return f"Removed maximum price filter (was {value})"
    
    elif field == "attributes":
        if isinstance(value, list) and value:
            items = ', '.join(str(v) for v in value[:3])  # Limit to first 3
            if len(value) > 3:
                items += f" and {len(value)-3} more"
            return f"Removed attribute filters ({items}) to broaden search"
        return "Removed attribute filters"
    
    elif field == "semantic_constraints":
        if isinstance(value, list) and value:
            items = ', '.join(str(v) for v in value[:3])
            if len(value) > 3:
                items += f" and {len(value)-3} more"
            return f"Broadened search terms (removed: {items})"
        return "Broadened search terms"
    
    elif field == "brand":
        return f"Expanded beyond {value} to include all brands - you might see similar products from other manufacturers"
    
    # category is intentionally excluded from the agent filter flow
    
    # Default fallback
    
    return f"Relaxed {field} filter (was: {value}) to help find results"