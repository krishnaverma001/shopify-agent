from difflib import get_close_matches
from typing import Optional, List

class BrandMapper:
    """Map fuzzy brand names to canonical brands"""
    
    def __init__(self, known_brands: List[str]):
        self.known_brands = [b.lower() for b in known_brands if b]
        self.canonical = {b.lower(): b for b in known_brands if b}
    
    def map_brand(self, extracted_brand: Optional[str]) -> Optional[str]:
        """Map extracted brand name to canonical brand"""
        
        if not extracted_brand:
            return None
        
        brand_lower = extracted_brand.lower()
        
        # Exact match (case-insensitive)
        if brand_lower in self.canonical:
            return self.canonical[brand_lower]
        
        # Fuzzy match
        matches = get_close_matches(brand_lower, self.known_brands, n=1, cutoff=0.7)
        if matches:
            return self.canonical[matches[0]]
        
        return None