from typing import List, Dict
from supabase import Client

def fetch_reviews(
    supabase: Client, 
    products: List[Dict]
) -> List[Dict]:
    """Fetch ALL reviews for the given products in ONE query"""
    
    if not products:
        return products
    
    handles = [p['product_handle'] for p in products]
    
    response = supabase.table("reviews") \
        .select("product_handle, rating, title, body, reviewer_name") \
        .in_("product_handle", handles) \
        .execute()
    
    # Group reviews by product
    reviews_by_handle = {}
    for review in response.data:
        handle = review['product_handle']
        if handle not in reviews_by_handle:
            reviews_by_handle[handle] = []
        reviews_by_handle[handle].append({
            'rating': review.get('rating'),
            'title': review.get('title'),
            'body': review.get('body'),
            'reviewer': review.get('reviewer_name')
        })
    
    # Attach reviews to products
    for product in products:
        handle = product['product_handle']
        reviews = reviews_by_handle.get(handle, [])
        product['reviews'] = reviews[:3]
        product['review_count'] = len(reviews)
        
        ratings = [r['rating'] for r in reviews if r['rating']]
        product['avg_rating'] = round(sum(ratings) / len(ratings), 1) if ratings else None
    
    return products

def rerank_with_reviews(products: List[Dict]) -> List[Dict]:
    """Re-rank products based on review signals"""
    
    for product in products:
        final_score = product['score']
        
        if product['review_count'] > 0:
            review_boost = min(0.1, product['review_count'] / 100)
            final_score += review_boost
        
        if product['avg_rating']:
            rating_boost = (product['avg_rating'] - 3) / 40
            final_score += rating_boost
        
        product['final_score'] = round(final_score, 4)
        product['score'] = product['final_score']
    
    products.sort(key=lambda x: x['final_score'], reverse=True)
    return products