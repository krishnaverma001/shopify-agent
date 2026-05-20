import hashlib

import pandas as pd
from typing import List, Dict
from app.data.processors.data_cleaner import DataCleaner

class ReviewLoader:
    """Load and parse review data from CSV"""
    
    def __init__(self, cleaner: DataCleaner = None):
        self.cleaner = cleaner or DataCleaner()
    
    def load_reviews(self, csv_path: str) -> List[Dict]:
        """Load reviews from CSV file"""
        print("Loading reviews from CSV...")
        
        df = pd.read_csv(csv_path)
        reviews = []
        
        for row in df.to_dict(orient="records"):
            review = self._create_review_record(row)
            reviews.append(review)
        
        print(f"Loaded {len(reviews)} reviews")
        return reviews
    
    def _create_review_record(self, row: Dict) -> Dict:
        """Create review dictionary from row data"""

        review_id = self.cleaner.clean_value(row.get("metaobject_handle"))
        product_id = self.cleaner.clean_value(row.get("product_id"))
        product_handle = self.cleaner.clean_value(row.get("product_handle"))
        reviewer_name = self.cleaner.clean_value(row.get("reviewer_name"))
        reviewer_email = self.cleaner.clean_value(row.get("reviewer_email"))
        title = self.cleaner.clean_value(row.get("title"))
        body = self.cleaner.clean_value(row.get("body"))
        review_date = self.cleaner.clean_value(row.get("review_date"))

        return {
            "review_id": review_id,
            "product_id": product_id,
            "product_handle": product_handle,
            "reviewer_name": reviewer_name,
            "reviewer_email": reviewer_email,
            "rating": int(row["rating"]) if pd.notna(row.get("rating")) else None,
            "title": title,
            "body": body,
            "review_date": review_date,
            "verified": str(row.get("verified", "")).lower() == "true"
        }