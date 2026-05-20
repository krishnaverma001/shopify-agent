from app.data.loaders.product_loader import ProductLoader
from app.data.loaders.review_loader import ReviewLoader
from app.embeddings.generator import EmbeddingGenerator
from app.db.repositories.product_repository import ProductRepository
from app.db.repositories.review_repository import ReviewRepository
from app.shopify.fetch_for_seed import ShopifyFetcher
from app.cache.brand_catalog import load_catalog_metadata
from .config import settings

import sys
import subprocess
import asyncio
from pathlib import Path
from typing import List, Dict

class DataPipeline:
    """Complete data pipeline for products and reviews"""
    
    def __init__(self):
        self.product_loader = ProductLoader()
        self.review_loader = ReviewLoader()
        self.embedder = EmbeddingGenerator()
        self.product_repo = ProductRepository()
        self.review_repo = ReviewRepository()
        self.shopify_fetcher = ShopifyFetcher()
    
    def _sync_shopify_ids(self, variants: List[Dict]):
        """Sync variants with Shopify to get real IDs"""
        
        print("Syncing with Shopify to get real variant IDs...")
        
        # Get variants that need syncing
        variants_to_sync = self.product_repo.get_variants_without_shopify_ids()
        
        if not variants_to_sync:
            print("All variants already synced!")
            return
        
        synced_count = 0
        for variant in variants_to_sync:
            sku = variant.get("sku")
            if not sku:
                continue
            
            try:
                # Fetch from Shopify
                result = asyncio.run(
                    self.shopify_fetcher.get_product_and_variant_by_sku(sku)
                )
                
                if result:
                    product_gid, product_id, variant_gid, variant_id = result
                    
                    # Update variant
                    if variant_gid:
                        self.product_repo.update_variant_shopify_ids(
                            variant_id=variant["variant_id"],
                            shopify_variant_id=variant_id,
                            shopify_gid=variant_gid
                        )
                        
                        # Update product too
                        if product_gid:
                            self.product_repo.update_product_shopify_ids(
                                handle=variant["product_handle"],
                                shopify_product_id=product_id,
                                shopify_gid=product_gid
                            )
                        
                        synced_count += 1
                        print(f"Synced: {sku} -> {variant_id}")
                        
            except Exception as e:
                print(f"Failed to sync SKU {sku}: {e}")
        
        print(f"Synced {synced_count}/{len(variants_to_sync)} variants")
        
    def run_product_pipeline(self, products_csv_path: str):
        # Load from CSV
        products, variants = self.product_loader.load_products(products_csv_path)
        
        # Store in Supabase
        self.product_repo.upsert_products(products)
        self.product_repo.upsert_variants(variants)
        
        # Sync with Shopify to get real IDs
        self._sync_shopify_ids(variants)
        
        # Generate embeddings
        texts, handles = self.embedder.prepare_embedding_texts(products, variants)
        embeddings = self.embedder.generate_embeddings(texts)
        product_payloads = self.embedder.create_embedding_payloads(handles, texts, embeddings)
        
        self.product_repo.upsert_product_embeddings(product_payloads)
        
        # Get sync counts for summary
        synced_variants = len(self.product_repo.get_variants_without_shopify_ids())
        total_variants = len(variants)
        
        print(f"Product pipeline complete!")
        print(f"  - {len(products)} products")
        print(f"  - {total_variants} variants total")
        print(f"  - {total_variants - synced_variants} variants synced with Shopify")
        print(f"  - {len(product_payloads)} embeddings\n")
    
    def run_review_pipeline(self, reviews_csv_path: str):
        """Process reviews: load → store → embed"""
        
        reviews = self.review_loader.load_reviews(reviews_csv_path)
        
        self.review_repo.upsert_reviews(reviews)
        
        texts, review_ids, product_handles = self.embedder.prepare_review_texts(reviews)
        embeddings = self.embedder.generate_embeddings(texts)
        review_payloads = self.embedder.create_review_payloads(
            review_ids, texts, product_handles, embeddings
        )
        
        self.review_repo.upsert_review_embeddings(review_payloads)
        
        print(f"\n✅ Review pipeline complete!")
        print(f"{len(reviews)} reviews")
        print(f"{len(review_payloads)} embeddings\n")
    
    def run_full_pipeline(self, products_csv_path: str, reviews_csv_path: str):
        """Run complete pipeline"""
        
        self.run_product_pipeline(products_csv_path)
        
        # load brands and optionally categories during seeding into memory cache for faster retrieval
        load_catalog_metadata()
        self.run_review_pipeline(reviews_csv_path)
        
        print("SEED DATA LOADED SUCCESSFULLY!")
        
class SetupCommand:
    """One-command setup for new users"""
    
    @staticmethod
    def run_migrations():
        """Run Supabase CLI migrations"""
        
        try:
            subprocess.run(["supabase", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Supabase CLI not found. Skipping migrations.")
            print("To install: https://supabase.com/docs/guides/local-development/cli")
            return
        
        # Check if supabase folder exists 
        if not Path("supabase").exists():
            print("Supabase not initialized. Run 'supabase init' first.")
            return
        
        # Push migrations to remote
        try:
            print("Pushing migrations to Supabase...")
            result = subprocess.run(
                ["supabase", "db", "push", "--yes"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print(" Migrations applied successfully")
            else:
                print(f"Migration warning: {result.stderr[:200]}")
                
        except Exception as e:
            print(f"Could not run migrations: {e}")
            print("Tables may already exist, continuing...")
    
    @staticmethod
    def check_environment():
        try:
            from app.config import settings
            
            _ = settings.SUPABASE_URL
            _ = settings.SUPABASE_PUBLIC_KEY
            _ = settings.PRODUCTS_CSV
            _ = settings.REVIEWS_CSV
            
            if not Path(settings.PRODUCTS_CSV).exists():
                print(f"Warning: Products CSV not found at {settings.PRODUCTS_CSV}")
            
            if not Path(settings.REVIEWS_CSV).exists():
                print(f"Warning: Reviews CSV not found at {settings.REVIEWS_CSV}")

            return True
        
        except Exception as e:
            print("Environment error:", e)
            return False
    
def main():
    """Complete setup: migrations + data loading"""
    
    print("Checking environment...")
    if not SetupCommand.check_environment():
        print("Setup failed. Please fix .env file and try again.")
        sys.exit(1)
    
    print("Running database migrations...")
    SetupCommand.run_migrations()
    
    print("Loading seed data...")
    pipeline = DataPipeline()

    pipeline.run_full_pipeline(
        products_csv_path=settings.PRODUCTS_CSV,
        reviews_csv_path=settings.REVIEWS_CSV
    )
    
    print("SETUP COMPLETE! Your database is ready!")

if __name__ == "__main__":
    main()