from typing import List, Dict
from app.db.supabase_client import SupabaseClient
from app.embeddings.models import EmbeddingPayload

class ProductRepository:
    """Handle all product-related database operations"""
    
    def __init__(self):
        self.client = SupabaseClient().get_client()
    
    def upsert_products(self, products: List[Dict]) -> None:
        """
        Insert or update products in the products table
        Args: products - List of product dictionaries from ProductLoader
        """
        if not products:
            return
        
        print(f"Upserting {len(products)} products...")
        
        # Upsert in batches to avoid timeout
        batch_size = 50
        for i in range(0, len(products), batch_size):
            batch = products[i: i + batch_size]
            self.client.table("products").upsert(
                batch,
                on_conflict="handle"
            ).execute()
        
        print(f"Products stored successfully")
    
    def upsert_variants(self, variants: List[Dict]) -> None:
        """
        Insert or update variants into product_variants table
        Args: variants - List of variant dictionaries from ProductLoader
        """
        if not variants:
            return
        
        print(f"Inserting {len(variants)} variants...")
        
        batch_size = 50
        
        for i in range(0, len(variants), batch_size):
            batch = variants[i: i + batch_size]
            self.client.table("product_variants").upsert(
                batch,
                on_conflict="variant_id"
            ).execute()
        
        print(f"Variants stored successfully")
    
    def upsert_product_embeddings(self, payloads: List[EmbeddingPayload]) -> None:
        """
        Store product embeddings in product_embeddings table
        Args: payloads - List of EmbeddingPayload objects
        """
        if not payloads:
            return
        
        print(f"Storing {len(payloads)} product embeddings...")
        
        # Convert payloads to dicts for insertion
        payload_dicts = [p.to_dict() for p in payloads]
        
        batch_size = 50
        for i in range(0, len(payload_dicts), batch_size):
            batch = payload_dicts[i: i + batch_size]
            self.client.table("product_embeddings").upsert(
                batch,
                on_conflict="product_handle"
            ).execute()
        
        print(f"Product embeddings stored successfully")
    
    def get_all_products(self) -> List[Dict]:
        """Fetch all products for embedding regeneration"""
        response = self.client.table("products").select(
            "handle, title, description, vendor, category, tags, product_type"
        ).execute()

        return response.data
    
    def get_all_variants(self) -> List[Dict]:
        """Fetch all variants for embedding regeneration"""
        response = self.client.table("product_variants").select(
            "variant_id, product_handle, option1_value, option2_value, option3_value"
        ).execute()

        return response.data
    

    
    def update_product_shopify_ids(self, handle: str, shopify_product_id: int, shopify_gid: str) -> None:
        """Update product with Shopify IDs"""
        self.client.table("products").update({
            "shopify_product_id": shopify_product_id,
            "shopify_gid": shopify_gid
        }).eq("handle", handle).execute()

    def update_variant_shopify_ids(self, variant_id: str, shopify_variant_id: int, shopify_gid: str) -> None:
        """Update variant with Shopify IDs"""
        self.client.table("product_variants").update({
            "shopify_variant_id": shopify_variant_id,
            "shopify_gid": shopify_gid
        }).eq("variant_id", variant_id).execute()

    def get_variants_without_shopify_ids(self) -> List[Dict]:
        """Get variants that need Shopify ID sync"""
        response = self.client.table("product_variants") \
            .select("variant_id, sku, product_handle") \
            .is_("shopify_gid", "null") \
            .neq("sku", "null") \
            .execute()
        return response.data

    def get_products_without_shopify_ids(self) -> List[Dict]:
        """Get products that need Shopify ID sync"""
        response = self.client.table("products") \
            .select("handle") \
            .is_("shopify_gid", "null") \
            .execute()
        return response.data
    
    def get_all_brands(self) -> List[str]:
        response = (
            self.client
            .table("products")
            .select("vendor")
            .execute()
        )

        return list({
            row["vendor"]
            for row in response.data
            if row.get("vendor")
        })