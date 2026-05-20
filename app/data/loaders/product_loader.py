import pandas as pd
import hashlib
from typing import List, Dict, Tuple
from app.data.processors.data_cleaner import DataCleaner

class ProductLoader:
    """Load and parse product data from CSV"""
    
    def __init__(self, cleaner: DataCleaner = None):
        self.cleaner = cleaner or DataCleaner()
    
    def load_products(self, csv_path: str) -> Tuple[List[Dict], List[Dict]]:
        """
        Load products and variants from CSV
        Returns: (products_list, variants_list)
        """
        print("Loading products from CSV...")
        
        df = pd.read_csv(csv_path)
        grouped = df.groupby("Handle")
        
        products = []
        variants = []
        
        for handle, group in grouped:
            first = group.iloc[0]
            
            # Create product record
            product = self._create_product_record(handle, first)
            products.append(product)
            
            # Create variant records
            product_variants = self._create_variant_records(handle, group)
            variants.extend(product_variants)
        
        print(f"Loaded {len(products)} products and {len(variants)} variants")
        return products, variants
    
    def _create_product_record(self, handle: str, first_row: pd.Series) -> Dict:
        """Create product dictionary from row data"""
        return {
            "handle": self.cleaner.clean_value(handle),
            "shopify_product_id": None,  
            "shopify_gid": None,
            "title": self.cleaner.clean_value(first_row.get("Title")),
            "description": self.cleaner.clean_html(first_row.get("Body (HTML)")),
            "vendor": self.cleaner.clean_value(first_row.get("Vendor")),
            "category": self.cleaner.clean_value(first_row.get("Product Category")),
            "product_type": self.cleaner.clean_value(first_row.get("Type")),
            "tags": self.cleaner.clean_value(first_row.get("Tags")),
            "image_url": self.cleaner.clean_value(first_row.get("Image Src")),
            "seo_title": self.cleaner.clean_value(first_row.get("SEO Title")),
            "seo_description": self.cleaner.clean_value(first_row.get("SEO Description")),
            "status": self.cleaner.clean_value(first_row.get("Status"))
        }
    
    def _create_variant_records(self, handle: str, group: pd.DataFrame) -> List[Dict]:
        """Create variant dictionaries from grouped rows"""
        variants = []
        
        for _, row in group.iterrows():
            variant = self._create_single_variant(handle, row)
            if variant:  # Only add non-empty variants
                variants.append(variant)
        
        return variants
    
    def _create_single_variant(self, handle: str, row: pd.Series) -> Dict:
        """Create single variant dictionary"""

        sku = self.cleaner.clean_value(row.get("Variant SKU"))
        price = row.get("Variant Price")
        option1 = self.cleaner.clean_value(row.get("Option1 Value"))
        option2 = self.cleaner.clean_value(row.get("Option2 Value"))
        option3 = self.cleaner.clean_value(row.get("Option3 Value"))

        variant_key = f"""
        {handle}|
        {sku}|
        {option1}|
        {option2}|
        {option3}
        """.strip()

        variant_id = hashlib.md5(
            variant_key.encode()
        ).hexdigest()
        
        # Skip fake/empty variants
        if self._is_empty_variant(sku, price, option1, option2, option3):
            return None
        
        return {
            "variant_id": variant_id,
            "shopify_variant_id": None,
            "product_handle": handle,
            "sku": sku,
            "price": float(price) if pd.notna(price) else None,
            "option1_name": self.cleaner.clean_value(row.get("Option1 Name")),
            "option1_value": option1,
            "option2_name": self.cleaner.clean_value(row.get("Option2 Name")),
            "option2_value": option2,
            "option3_name": self.cleaner.clean_value(row.get("Option3 Name")),
            "option3_value": option3,
            "variant_image": self.cleaner.clean_value(row.get("Variant Image"))
        }
    
    @staticmethod
    def _is_empty_variant(sku, price, opt1, opt2, opt3) -> bool:
        """Check if variant has no meaningful data"""
        return (sku is None and 
                pd.isna(price) and 
                opt1 is None and 
                opt2 is None and 
                opt3 is None)