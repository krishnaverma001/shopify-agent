from typing import List, Dict
from supabase import Client

def vector_search(
    supabase: Client, 
    query_embedding: List[float]
) -> List[Dict]:
    """Vector similarity search - all products with score > 0.2"""
    
    response = supabase.rpc(
        'match_products',
        {
            'query_embedding': query_embedding,
            'match_threshold': 0.15,
            'match_count': 50
        }
    ).execute()
    
    results = []
    for idx, item in enumerate(response.data):
        results.append({
            'product_handle': item['product_handle'],
            'shopify_product_id': item.get('shopify_product_id'),
            'shopify_gid': item.get('shopify_gid'),
            'rank': idx + 1,
            'vector_score': float(item['similarity']),
            'title': item.get('title'),
            'description': item.get('description'),
            'vendor': item.get('vendor'),
            'category': item.get('category'),
            'min_price': item.get('min_price'),
            'image_url': item.get('image_url')
        })
    
    return results