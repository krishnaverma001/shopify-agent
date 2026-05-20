from app.agents.state import ConversationState
from langchain_core.messages import AIMessage
import random

def reset_node(state: ConversationState) -> ConversationState:
    """Clear all conversation state and start fresh."""
    
    responses = [
        "Sure, let's start fresh. What would you like to look for?",
        "No problem. How can I help you?",
        "Got it. Ready to help with a new search.",
        "Alright, let's try something else. What are you looking for?",
        "Okay, reset. What would you like me to search for?",
    ]
    
    text = random.choice(responses)
    
    # Clear EVERYTHING
    return {
        "messages": state.get("messages", []) + [AIMessage(content=text)],
        "turn_count": state.get("turn_count", 0) + 1,
        
        # Clear all search/filter state
        "raw_query": "",
        "normalized_query": "",
        "retrieval_query": "",
        "brand": None,
        "min_price": None,
        "max_price": None,
        "min_rating": None,
        "attributes": [],
        "semantic_constraints": [],
        "brand_was_explicit": False,
        "search_results": [],
        "similar_products": [],
        "detail_product": None,
        "comparison": None,
        "search_attempts": 0,
        "relaxation_budget": 3,
        "relaxation_log": [],
        "drop_field": None,
        "constraint_history": [],
        "needs_clarification": False,
        "clarification_question": None,
        "awaiting_user_response": False,
        "pending_clarification_field": None,
        "quick_response": None,
        "next_action": "reset",
        "response_payload": None,
    }