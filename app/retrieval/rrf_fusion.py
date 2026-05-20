from typing import List, Dict

def rrf_fusion(
    vector_results: List[Dict], 
    keyword_results: List[Dict],
    rrf_k: int = 60
) -> List[Dict]:
    """Reciprocal Rank Fusion - combines rankings without relying on absolute scores"""
    
    rrf_scores = {}
    product_data = {}
    
    # Process vector results
    for r in vector_results:
        handle = r['product_handle']
        rrf_scores[handle] = 1 / (rrf_k + r['rank'])
        product_data[handle] = {
            'product_handle': handle,
            'shopify_product_id': r.get('shopify_product_id'),
            'shopify_gid': r.get('shopify_gid'),
            'title': r.get('title'),
            'description': r.get('description'),
            'vendor': r.get('vendor'),
            'category': r.get('category'),
            'min_price': r.get('min_price'),
            'image_url': r.get('image_url'),
            'vector_rank': r['rank'],
            'vector_score': r.get('vector_score', 0),
            'keyword_rank': None,
            'keyword_score': 0
        }
    
    # Process keyword results
    for r in keyword_results:
        handle = r['product_handle']
        rrf_scores[handle] = rrf_scores.get(handle, 0) + (1 / (rrf_k + r['rank']))
        
        if handle in product_data:
            if not product_data[handle].get('shopify_gid'):
                product_data[handle]['shopify_gid'] = r.get('shopify_gid')
                product_data[handle]['shopify_product_id'] = r.get('shopify_product_id'),

                
            product_data[handle]['keyword_rank'] = r['rank']
            product_data[handle]['keyword_score'] = r.get('keyword_score', 0)
            
            if not product_data[handle].get('min_price'):
                product_data[handle]['min_price'] = r.get('min_price')
            if not product_data[handle].get('image_url'):
                product_data[handle]['image_url'] = r.get('image_url')
        else:
            product_data[handle] = {
                'product_handle': handle,
                'shopify_gid': r.get('shopify_gid'),
                'shopify_product_id': r.get('shopify_product_id'),

                'title': r.get('title'),
                'description': r.get('description'),
                'vendor': r.get('vendor'),
                'category': r.get('category'),
                'min_price': r.get('min_price'),
                'image_url': r.get('image_url'),
                'vector_rank': None,
                'vector_score': 0,
                'keyword_rank': r['rank'],
                'keyword_score': r.get('keyword_score', 0)
            }
    
    # Build results sorted by RRF score
    results = []
    for handle, score in rrf_scores.items():
        data = product_data[handle]
        results.append({
            'product_handle': handle,
            
            'shopify_product_id': data.get('shopify_product_id'),
            'shopify_gid': data.get('shopify_gid'),

            'score': round(score * 100, 4),
            'title': data['title'],
            'description': data['description'],
            'vendor': data['vendor'],
            'category': data['category'],
            'min_price': data.get('min_price'),
            'image_url': data.get('image_url'),
            'avg_rating': None,
            'review_count': 0,
            'reviews': [],
            'vector_rank': data['vector_rank'],
            'keyword_rank': data['keyword_rank']
        })
    
    results.sort(key=lambda x: x['score'], reverse=True)
    return results