import re
from typing import Optional

class QueryNormalizer:
    """Clean and normalize user query before LLM parsing"""
    
    def normalize(self, query: str) -> str:
        """Normalize query: lowercase, trim, fix common typos"""
        
        # Lowercase
        normalized = query.lower()
        
        # Trim whitespace
        normalized = normalized.strip()
        
        # Remove extra spaces
        normalized = re.sub(r'\s+', ' ', normalized)
        
        return normalized