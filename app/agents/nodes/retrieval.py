from app.retrieval.hybrid import HybridRetriever
from app.agents.state import ConversationState
from app.logging import get_logger

logger = get_logger(__name__)

def _get_retriever() -> HybridRetriever:
    return HybridRetriever()

def retrieval_node(state: ConversationState) -> ConversationState:
    """Run hybrid search with current state filters."""
    
    retriever = _get_retriever()
    
    retrieval_query = state.get("retrieval_query", "")
    brand = state.get("brand")
    min_price = state.get("min_price")
    max_price = state.get("max_price")
    min_rating = state.get("min_rating")
    
    logger.info(f"Query = '{retrieval_query}' brand = {brand} price = {min_price}-{max_price} rating ≥ {min_rating}")
    
    results = retriever.search(
        query_text=retrieval_query,
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        limit=20,
    )
    
    # If no results, try without any filters 
    if len(results) == 0 and (brand or min_price or max_price or min_rating):
        logger.error("No results with filters, trying without filters")
        
        results = retriever.search(
            query_text=retrieval_query,
            brand=None,
            min_price=None,
            max_price=None,
            min_rating=None,
            limit=20,
        )

        if len(results) > 0:
            logger.info(f"Found {len(results)} results after removing filters")
            
            return {
                **state,
                "search_results": results,
                "search_attempts": state.get("search_attempts", 0) + 1,
                "brand": None,
                "min_price": None,
                "max_price": None,
                "min_rating": None,
            }
    
    attempts = state.get("search_attempts", 0) + 1
    logger.info(f"Attempt #{attempts} -> {len(results)} results")
    
    return {
        **state,
        "search_results": results,
        "search_attempts": attempts,
    }