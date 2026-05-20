# app/embeddings/generator.py

from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
from app.data.processors.data_cleaner import DataCleaner
from app.config import settings
from .models import EmbeddingPayload, ReviewEmbeddingPayload

class EmbeddingGenerator:
    """Generate embeddings for products"""
    
    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.embedder = SentenceTransformer(settings.EMBEDDING_MODEL)
        self.cleaner = DataCleaner()
    
    def prepare_embedding_texts(self, products: List[Dict], variants: List[Dict]) -> Tuple[List[str], List[str]]:
        """Prepare text for embedding generation"""
        
        # Group variants by product handle
        variant_map = self._group_variants_by_product(variants)
        
        texts = []
        handles = []
        
        for product in products:
            handle = product["handle"]
            variants_text = self._get_variant_text(handle, variant_map)
            
            # Combine all product information
            text = self._build_embedding_text(product, variants_text)
            
            texts.append(text)
            handles.append(handle)
        
        return texts, handles
    
    def _group_variants_by_product(self, variants: List[Dict]) -> Dict[str, List[str]]:
        """Group variants by product handle"""
        variant_map = {}
        
        for variant in variants:
            handle = variant["product_handle"]
            variant_values = self._extract_variant_values(variant)
            
            if handle not in variant_map:
                variant_map[handle] = []
            
            if variant_values:
                variant_map[handle].append(variant_values)
        
        return variant_map
    
    def _extract_variant_values(self, variant: Dict) -> str:
        """Extract meaningful values from variant"""

        parts = []

        if variant.get("option1_name") and variant.get("option1_value"):
            parts.append(
                f"{variant['option1_name']}: {variant['option1_value']}"
            )

        if variant.get("option2_name") and variant.get("option2_value"):
            parts.append(
                f"{variant['option2_name']}: {variant['option2_value']}"
            )

        if variant.get("option3_name") and variant.get("option3_value"):
            parts.append(
                f"{variant['option3_name']}: {variant['option3_value']}"
            )

        return " | ".join(parts)
    
    def _get_variant_text(self, handle: str, variant_map: Dict) -> str:
        """Get combined variant text for a product"""
        variants = variant_map.get(handle, [])
        unique_variants = list(dict.fromkeys(variants))
        return " | ".join(unique_variants)
    
    def _build_embedding_text(self, product: Dict, variants_text: str) -> str:
        """Build the text that will be embedded"""
        # text = f"""
        # Title: {product.get('title', '')}
        # Vendor: {product.get('vendor', '')}
        # Category: {product.get('category', '')}
        # Tags: {product.get('tags', '')}
        # Description: {product.get('description', '')}
        # Variants: {variants_text}
        # """

        parts = [
            product.get("title", ""),
            product.get("vendor", ""),
            product.get("category", ""),
            product.get("tags", ""),
            product.get("description", ""),
            variants_text
        ]

        text = " ".join(str(x) for x in parts if x)
        
        # Clean and normalize
        text = self.cleaner.normalize_text(text)
        
        # Truncate to reasonable length (4000 chars)
        return text[:4000]
    
    def create_embedding_payloads(self, handles: List[str], texts: List[str], 
                                  embeddings: List[List[float]]) -> List[EmbeddingPayload]:
        """Create payload objects for database insertion"""
        payloads = []
        
        for handle, text, embedding in zip(handles, texts, embeddings):
            payloads.append(EmbeddingPayload(
                product_handle=handle,
                searchable_text=text,
                embedding=embedding.tolist() if hasattr(embedding, 'tolist') else embedding
            ))
        
        return payloads
    
    def generate_embeddings(self, texts: List[str], batch_size: int = None) -> List[List[float]]:
        """Generate embeddings for a list of texts"""
        batch_size = batch_size or settings.BATCH_SIZE
        
        print(f"Generating embeddings for {len(texts)} texts...")
        
        embeddings = self.embedder.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True
        )
        
        return embeddings

    def prepare_review_texts(self, reviews: List[Dict]) -> Tuple[List[str], List[str], List[str]]:
        """Prepare review text for embedding"""
        texts = []
        review_ids = []
        product_handles = []
         
        for review in reviews:

            review_id = review["review_id"]

            # Build text for embedding
            text = self._build_review_text(review)
            
            texts.append(text)
            review_ids.append(review_id)
            product_handles.append(review['product_handle'])
        
        return texts, review_ids, product_handles
    
    def _build_review_text(self, review: Dict) -> str:
        """Build text for review embedding"""

        verified = "Yes" if review.get("verified") else "No"

        text = f"""
        Product: {review.get('product_handle', '')}
        Rating: {review.get('rating', '')}/5
        Title: {review.get('title', '')}
        Review: {review.get('body', '')}
        Verified Purchase: {verified}
        """
        
        # Reuse existing cleaning method
        text = self.cleaner.normalize_text(text)
        return text[:2000]  # Reviews are shorter
    
    def create_review_payloads(self, review_ids: List[str], texts: List[str], 
                               product_handles: List[str], embeddings: List[List[float]]) -> List[Dict]:
        """Create payloads for database insertion"""
        payloads = []
        
        for review_id, text, handle, embedding in zip(review_ids, texts, product_handles, embeddings):
            payloads.append(
                ReviewEmbeddingPayload(
                    review_id=review_id,
                    product_handle=handle,
                    searchable_text=text,
                    embedding=embedding.tolist() if hasattr(embedding, 'tolist') else embedding
                )
            )
        
        return payloads