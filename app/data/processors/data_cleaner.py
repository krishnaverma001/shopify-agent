import re
from html import unescape
import pandas as pd

class DataCleaner:
    """Handles all data cleaning operations"""
    
    @staticmethod
    def clean_html(text):
        """Remove HTML tags and clean HTML content"""
        
        if pd.isna(text):
            return ""
        
        text = unescape(str(text))
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
    
    @staticmethod
    def clean_value(val):
        """Clean and standardize values"""
        
        if pd.isna(val):
            return None
        return str(val).strip()
    
    @staticmethod
    def normalize_text(text):
        """Normalize text for embeddings"""
        
        if not text:
            return ""
        text = text.lower()
        text = re.sub(r"\s+", " ", text)
        return text.strip()