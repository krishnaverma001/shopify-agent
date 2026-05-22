from dataclasses import dataclass, field
from typing import Optional, List
# from enum import Enum

# class Intent(str, Enum):
#     SEARCH = "search"
#     COMPARE = "compare"
#     DETAILS = "details"
#     SIMILAR = "similar"

@dataclass
class ParsedQuery:
    """Structured query after LLM parsing + validation"""
    
    # Original
    raw_query: str
    
    # Normalized
    normalized_query: str = ""
    
    # Core
    # intent: Intent = Intent.SEARCH
    retrieval_query: str = ""  # For retrieval (filters removed)
    
    # Filters
    brand: Optional[str] = None
    # category: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_rating: Optional[float] = None
    
    # Semantic
    attributes: List[str] = field(default_factory=list)
    semantic_constraints: List[str] = field(default_factory=list)
    
    # Validation status
    valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "raw_query": self.raw_query,
            "normalized_query": self.normalized_query,
            "intent": self.intent.value,
            "retrieval_query": self.retrieval_query,
            "brand": self.brand,
            "category": self.category,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "min_rating": self.min_rating,
            "attributes": self.attributes,
            "semantic_constraints": self.semantic_constraints,
            "valid": self.valid
        }