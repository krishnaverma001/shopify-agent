from typing import List, Optional
from app.understanding.models import ParsedQuery, Intent
from app.understanding.brand_map import BrandMapper

class QueryValidator:
    """Validate and map extracted data from LLM"""
    
    def __init__(self, known_brands: List[str]):
        self.brand_mapper = BrandMapper(known_brands)
    
    def validate(self, parsed: ParsedQuery, extracted: dict) -> ParsedQuery:
        """Validate and clean extracted data"""
        
        errors = []
        
        # Validate Intent 
        intent = extracted.get("intent", "search")
        if intent in [i.value for i in Intent]:
            parsed.intent = Intent(intent)
        else:
            parsed.intent = Intent.SEARCH
            errors.append(f"Unknown intent '{intent}', defaulting to search")
        
        # Validate Clean Query 
        retrieval_query = extracted.get("retrieval_query", "")
        retrieval_query = retrieval_query.strip() if retrieval_query else ""

        parsed.retrieval_query = retrieval_query if retrieval_query else parsed.raw_query
        
        # Map Brand 
        raw_brand = extracted.get("brand")
        mapped_brand = self.brand_mapper.map_brand(raw_brand)
        
        if mapped_brand:
            parsed.brand = mapped_brand
        elif raw_brand:
            errors.append(f"Brand '{raw_brand}' not recognized")
        
        # Validate Price 
        min_price = extracted.get("min_price")
        if min_price is not None:
            try:
                min_price = float(min_price)
                if min_price >= 0:
                    parsed.min_price = min_price
                else:
                    errors.append(f"Min price {min_price} is negative")
            except (TypeError, ValueError):
                errors.append(f"Invalid min price: {min_price}")
        
        max_price = extracted.get("max_price")
        if max_price is not None:
            try:
                max_price = float(max_price)
                if max_price >= 0:
                    parsed.max_price = max_price
                else:
                    errors.append(f"Max price {max_price} is negative")
            except (TypeError, ValueError):
                errors.append(f"Invalid max price: {max_price}")
        
        # Fix swapped min/max
        if parsed.min_price is not None and parsed.max_price is not None and parsed.min_price > parsed.max_price:
            errors.append(f"Min price (${parsed.min_price}) > max price (${parsed.max_price}), swapping")
            parsed.min_price, parsed.max_price = parsed.max_price, parsed.min_price
        
        # Validate Rating 
        min_rating = extracted.get("min_rating")
        if min_rating is not None:
            try:
                min_rating = float(min_rating)
                if 1.0 <= min_rating <= 5.0:
                    parsed.min_rating = min_rating
                else:
                    errors.append(f"Rating {min_rating} out of range (1-5)")
            except (TypeError, ValueError):
                errors.append(f"Invalid rating: {min_rating}")
        
        # Validate Attributes 
        attributes = extracted.get("attributes", [])
        if isinstance(attributes, list):
            parsed.attributes = [str(a).lower() for a in attributes if a]
        else:
            errors.append(f"Invalid attributes format: {attributes}")
        
        # Validate Semantic Constraints 
        semantic_constraints = extracted.get("semantic_constraints", [])
        if isinstance(semantic_constraints, list):
            parsed.semantic_constraints = [str(s).lower() for s in semantic_constraints if s]
        else:
            errors.append(f"Invalid semantic constraints format: {semantic_constraints}")
        
        # Set Validation Status
        parsed.valid = len(errors) == 0
        parsed.validation_errors = errors
        
        if errors:
            print(f"Validation errors: {errors}")
        
        return parsed