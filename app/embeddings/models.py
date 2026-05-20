from typing import List
from dataclasses import dataclass

@dataclass
class EmbeddingPayload:
    """Data structure for product embedding payload"""
    
    product_handle: str
    searchable_text: str
    embedding: List[float]
    
    def to_dict(self):
        return {
            "product_handle": self.product_handle,
            "searchable_text": self.searchable_text,
            "embedding": self.embedding
        }
    
@dataclass
class ReviewEmbeddingPayload:
    """Data structure for review embedding payload"""

    review_id: str
    product_handle: str
    searchable_text: str
    embedding: List[float]

    def to_dict(self):
        return {
            "review_id": self.review_id,
            "product_handle": self.product_handle,
            "searchable_text": self.searchable_text,
            "embedding": self.embedding
        }