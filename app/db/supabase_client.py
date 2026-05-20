from supabase import create_client, Client
from app.config import settings


class SupabaseClient:
    """Singleton Supabase client wrapper"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_KEY
            )
        return cls._instance
    
    def get_client(self) -> Client:
        """Get the Supabase client instance"""
        return self.client