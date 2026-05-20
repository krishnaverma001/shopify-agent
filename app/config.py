# app/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent 
DATA_DIR = BASE_DIR / "app" / "data" / "seed"
MODELS_DIR = BASE_DIR / "models"

class Settings(BaseSettings):
    APP_NAME: str = "AI Shopping Agent"
    ENVIRONMENT: str = "development"

    PRODUCTS_CSV: Path = DATA_DIR / "products.csv"
    REVIEWS_CSV: Path = DATA_DIR / "reviews.csv" 
    CUSTOMERS_CSV: Path = DATA_DIR / "customers.csv" 
    ORDERS_CSV: Path = DATA_DIR / "orders.csv"

    DATABASE_URL: str = "data/shopify.db"
    VECTOR_DB_URL: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"
    
    SHOPIFY_STORE_DOMAIN: str = ""
    SHOPIFY_API_KEY: str = ""
    SHOPIFY_API_SECRET: str = ""
    SHOPIFY_ACCESS_TOKEN: str = ""
    SHOPIFY_API_VERSION: str = ""
    
    SUPABASE_URL: str = ""
    SUPABASE_PUBLIC_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    
    GROQ_API_KEY: str = ""
    
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    # LOCAL_EMBEDDING_MODEL_PATH: Path = (MODELS_DIR / EMBEDDING_MODEL)

    BATCH_SIZE: int = 32
    
    SECRET_KEY: str = ""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

settings = Settings()