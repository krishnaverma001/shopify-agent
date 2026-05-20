from typing import List, Dict
from supabase import Client

def enrich_with_prices(
    supabase: Client, 
    products: List[Dict]
) -> List[Dict]:
    """Ensure all products have min_price by fetching from variants table"""
    
    # Find products missing prices
    handles_needing_prices = [
        p['product_handle'] for p in products 
        if not p.get('min_price')
    ]
    
    if not handles_needing_prices:
        return products
    
    # Bulk fetch prices for missing products
    response = supabase.table("product_variants") \
        .select("product_handle, price") \
        .in_("product_handle", handles_needing_prices) \
        .execute()
    
    # Calculate min price per product
    price_map = {}
    for variant in response.data:
        handle = variant['product_handle']
        price = variant.get('price')
        if handle not in price_map or (price and price < price_map[handle]):
            price_map[handle] = price
    
    # Update products
    for product in products:
        handle = product['product_handle']
        if not product.get('min_price') and handle in price_map:
            product['min_price'] = price_map[handle]
    
    return products