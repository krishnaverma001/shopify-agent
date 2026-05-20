from typing import List, Dict, Optional

def apply_filters(
    products: List[Dict],
    brand: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None
) -> List[Dict]:
    """Apply post-retrieval filters to product list"""
    
    filtered = products
    
    # Brand filter (case-insensitive partial match)
    if brand:
        brand_lower = brand.lower()
        filtered = [
            p for p in filtered 
            if p.get('vendor') and brand_lower in p['vendor'].lower()
        ]
    
    # Price filters
    if min_price is not None:
        filtered = [
            p for p in filtered 
            if p.get('min_price') and p['min_price'] >= min_price
        ]
    
    if max_price is not None:
        filtered = [
            p for p in filtered 
            if p.get('min_price') and p['min_price'] <= max_price
        ]
    
    return filtered