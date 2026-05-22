from typing import List, Dict, Optional
from supabase import Client
from sentence_transformers import SentenceTransformer
import threading

from app.db.supabase_client import SupabaseClient
from app.config import settings
from app.logging import get_logger
from app.retrieval.vector_search import vector_search
from app.retrieval.keyword_search import keyword_search
from app.retrieval.rrf_fusion import rrf_fusion
from app.retrieval.filters import apply_filters
from app.retrieval.price_enrichment import enrich_with_prices
from app.retrieval.reviews import fetch_reviews, rerank_with_reviews
from app.retrieval.product_details import get_product_details, get_similar_products

logger = get_logger(__name__)

class HybridRetriever:
    """One instance, one embedder, one Supabase client"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, rrf_k: int = 60):
        if hasattr(self, '_initialized'):
            return
        
        logger.info("Initializing Hybrid Retriever")
        self.rrf_k = rrf_k
        
        logger.info("Connecting to Supabase")
        self.supabase: Client = SupabaseClient().get_client()
        
        logger.info("Loading embedding model")
        self.embedder = SentenceTransformer(settings.EMBEDDING_MODEL)
        
        self._initialized = True
        print("Hybrid Retriever ready")
    
    def search(
        self, 
        query_text: str,
        limit: int = 10,
        brand: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_rating: Optional[float] = None
    ) -> List[Dict]:
        """Complete search pipeline with filters"""
        
        logger.info(f"Searching: '{query_text}'")
        logger.info(f"Filters: brand={brand}, price={min_price}-{max_price}, rating≥{min_rating}")
        
        query_embedding = self.embedder.encode([query_text])[0].tolist()
        
        vector_results = vector_search(self.supabase, query_embedding)
        keyword_results = keyword_search(self.supabase, query_text)
        
        logger.info(f"Vector products: {len(vector_results)}, Keyword products: {len(keyword_results)}")
        
        fused_products = rrf_fusion(vector_results, keyword_results, self.rrf_k)
        logger.info(f"RRF fused: {len(fused_products)} unique products")
        
        fused_products = enrich_with_prices(self.supabase, fused_products)
        
        filtered_products = apply_filters(
            fused_products,
            brand=brand,
            min_price=min_price,
            max_price=max_price
        )
        logger.info(f"After filters: {len(filtered_products)} products")
        
        if not filtered_products:
            # logger.info("No products after filtering")
            return []
        
        candidates = filtered_products[:limit * 3]
        candidates = fetch_reviews(self.supabase, candidates)
        
        if min_rating:
            candidates = [
                p for p in candidates 
                if p.get('avg_rating') and p['avg_rating'] >= min_rating
            ]
            print(f"After rating filter (≥{min_rating} ⭐): {len(candidates)} products")
        
        final_results = rerank_with_reviews(candidates)
        
        logger.info(f"Final: {len(final_results[:limit])} products")
        return final_results[:limit]
    
    def get_product_details(self, product_handle: str) -> Dict:
        """Get detailed product information"""
        return get_product_details(self.supabase, product_handle)
    
    def get_similar_products(self, product_handle: str, limit: int = 10) -> List[Dict]:
        """Get similar products"""
        return get_similar_products(self.supabase, product_handle, limit)