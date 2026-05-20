from typing import List, Dict
from app.db.supabase_client import SupabaseClient
from app.embeddings.models import ReviewEmbeddingPayload

class ReviewRepository:
    """Handle all review-related database operations"""
    
    def __init__(self):
        self.client = SupabaseClient().get_client()
    
    def upsert_reviews(self, reviews: List[Dict]) -> None:
        """
        Upsert reviews into reviews table
        Args: reviews - List of review dictionaries from ReviewLoader
        """
        if not reviews:
            return
        
        print(f"Inserting {len(reviews)} reviews...")
        
        batch_size = 100
        for i in range(0, len(reviews), batch_size):
            batch = reviews[i: i + batch_size]
            self.client.table("reviews").upsert(
                batch,
                on_conflict="review_id"
            ).execute()
        
        print(f"Reviews stored successfully")
    
    def upsert_review_embeddings(self, payloads: List[ReviewEmbeddingPayload]) -> None:
        """
        Store review embeddings in review_embeddings table
        Args: payloads - List of ReviewEmbeddingPayload objects
        """
        if not payloads:
            return
        
        print(f"Storing {len(payloads)} review embeddings...")
        
        # Convert payloads to dicts for insertion
        payload_dicts = [p.to_dict() for p in payloads]
        
        batch_size = 100
        for i in range(0, len(payload_dicts), batch_size):
            batch = payload_dicts[i: i + batch_size]
            self.client.table("review_embeddings").upsert(
                batch,
                on_conflict="review_id"
            ).execute()
        
        print(f"Review embeddings stored successfully")
    
    def get_all_reviews(self) -> List[Dict]:
        """Fetch all reviews for embedding regeneration"""
        response = self.client.table("reviews").select(
            "review_id, product_id, product_handle, rating, title, body, review_date, reviewer_name, reviewer_email, verified"
        ).execute()

        return response.data