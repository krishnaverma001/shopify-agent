from typing import List, Dict
from supabase import Client

def get_product_details(
    supabase: Client, 
    product_handle: str
) -> Dict:
    """Get detailed product information with all reviews"""
    
    # Fetch product details
    response = supabase.table("products") \
        .select("*") \
        .eq("handle", product_handle) \
        .execute()
    
    if not response.data:
        return None
    
    product = response.data[0]
    
    # Fetch all variants with prices
    variants_response = supabase.table("product_variants") \
        .select("shopify_variant_id, shopify_gid, sku, price, option1_name, option1_value, option2_name, option2_value, option3_name, option3_value") \
        .eq("product_handle", product_handle) \
        .execute()
    
    variants = variants_response.data
    
    # Calculate min and max prices
    prices = [v['price'] for v in variants if v.get('price')]
    min_price = min(prices) if prices else None
    max_price = max(prices) if prices else None
    
    # Fetch all reviews
    reviews_response = supabase.table("reviews") \
        .select("rating, title, body, reviewer_name, review_date") \
        .eq("product_handle", product_handle) \
        .execute()
    
    reviews = reviews_response.data
    
    ratings = [r['rating'] for r in reviews if r.get('rating')]
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None
    
    return {
        'product_handle': product['handle'],
        'shopify_gid': product['shopify_gid'],
        'shopify_product_id': product['shopify_product_id'],

        'title': product.get('title'),
        'description': product.get('description'),
        'vendor': product.get('vendor'),
        'min_price': min_price,
        'max_price': max_price,
        'price_range': (
            f"${min_price:.2f} - ${max_price:.2f}"
            if min_price and max_price and min_price != max_price
            else f"${min_price:.2f}" if min_price else None
        ),
        'variants': variants,
        'category': product.get('category'),
        'tags': product.get('tags'),
        'image_url': product.get('image_url'),
        'avg_rating': avg_rating,
        'total_reviews': len(reviews),
        'reviews': reviews[:10]
    }

def get_similar_products(
    supabase: Client, 
    product_handle: str, 
    limit: int = 5
) -> List[Dict]:
    """Get similar products using vector similarity"""
    
    response = supabase.rpc(
        "get_similar_products",
        {
            "product_handle": product_handle,
            "match_count": limit
        }
    ).execute()
    
    return response.data