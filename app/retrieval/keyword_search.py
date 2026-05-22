from typing import List, Dict
from supabase import Client

from app.logging import get_logger

logger = get_logger(__name__)

def keyword_search(
    supabase: Client, 
    query_text: str
) -> List[Dict]:
    """Keyword search using PostgreSQL full-text search ranking"""
    
    try:
        response = supabase.rpc(
            'keyword_search_products',
            {
                'search_query': query_text,
                'match_limit': 50
            }
        ).execute()
        
        results = []
        for item in response.data:
            results.append({
                'product_handle': item['product_handle'],
                'shopify_product_id': item.get('shopify_product_id'),
                'shopify_gid': item.get('shopify_gid'),
                'rank': item['rank'],
                'keyword_score': float(item['keyword_score']),
                'title': item.get('title'),
                'description': item.get('description'),
                'vendor': item.get('vendor'),
                'category': item.get('category'),
                'min_price': item.get('min_price'),
                'image_url': item.get('image_url')
            })
        
        return results
        
    except Exception as e:
        logger.error(f"Keyword search error: {e}, falling back to simple search")
        return _fallback_keyword_search(supabase, query_text)

def _fallback_keyword_search(
    supabase: Client, 
    query_text: str
) -> List[Dict]:
    """Fallback when FTS fails - simple ILIKE search"""
    
    response = supabase.table("products") \
        .select("handle, shopify_product_id, shopify_gid, title, description, vendor, category, image_url") \
        .ilike("handle", f"%{query_text.replace(' ', '%')}%") \
        .execute()
    
    handles = [item['handle'] for item in response.data]
    min_prices = {}
    if handles:
        price_response = supabase.table("product_variants") \
            .select("product_handle, price") \
            .in_("product_handle", handles) \
            .execute()
        
        for variant in price_response.data:
            handle = variant['product_handle']
            price = variant.get('price')
            if handle not in min_prices or (price and price < min_prices[handle]):
                min_prices[handle] = price
    
    results = []
    tokens = query_text.lower().split()
    
    for idx, item in enumerate(response.data, 1):
        score = 0
        if item.get('vendor') and any(t in item['vendor'].lower() for t in tokens):
            score += 3
        if item.get('title') and any(t in item['title'].lower() for t in tokens):
            score += 1
            
        results.append({
            'product_handle': item['handle'],
            'shopify_product_id': item.get('shopify_product_id'),
            'shopify_gid': item.get('shopify_gid'),
            'rank': idx,
            'keyword_score': score,
            'title': item.get('title'),
            'description': item.get('description'),
            'vendor': item.get('vendor'),
            'category': item.get('category'),
            'min_price': min_prices.get(item['handle']),
            'image_url': item.get('image_url')
        })
    
    results.sort(key=lambda x: x['keyword_score'], reverse=True)
    for idx, item in enumerate(results, 1):
        item['rank'] = idx
    
    return results[:50]