from typing import List, Dict

def rrf_fusion(
    vector_results: List[Dict],
    keyword_results: List[Dict],
    rrf_k: int = 60
) -> List[Dict]:
    """Reciprocal Rank Fusion - combine vector and BM25 results"""
    
    scores = {}
    products = {}
    
    # Process vector results
    for rank, item in enumerate(vector_results[:50], 1):
        handle = item['product_handle']
        scores[handle] = 1 / (rrf_k + rank)
        products[handle] = {
            'product_handle': handle,
            'title': item.get('title'),
            'vendor': item.get('vendor'),
            'category': item.get('category'),
            'min_price': item.get('min_price'),
            'image_url': item.get('image_url'),
            'vector_score': item.get('vector_score', 0),
            'keyword_score': 0
        }
    
    # Process keyword results
    for rank, item in enumerate(keyword_results[:50], 1):
        handle = item['product_handle']
        scores[handle] = scores.get(handle, 0) + 1 / (rrf_k + rank)
        
        if handle in products:
            products[handle]['keyword_score'] = item.get('keyword_score', 0)
            if not products[handle].get('min_price'):
                products[handle]['min_price'] = item.get('min_price')
        else:
            products[handle] = {
                'product_handle': handle,
                'title': item.get('title'),
                'vendor': item.get('vendor'),
                'category': item.get('category'),
                'min_price': item.get('min_price'),
                'image_url': item.get('image_url'),
                'vector_score': 0,
                'keyword_score': item.get('keyword_score', 0)
            }
    
    # Sort by RRF score
    results = []
    for handle, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        p = products[handle]
        results.append({
            **p,
            'rrf_score': round(score * 100, 4)
        })
    
    return results