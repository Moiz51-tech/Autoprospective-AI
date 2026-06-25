from supabase import create_client, Client
from config import settings
from utils.logger import get_logger

log = get_logger("supabase")

_client: Client = None


def get_supabase() -> Client:
    """Get or create the Supabase client (singleton)."""
    global _client
    if _client is None:
        try:
            if settings.supabase_url == "https://placeholder.supabase.co":
                log.warning("Supabase URL is placeholder — DB operations will fail")
            _client = create_client(settings.supabase_url, settings.supabase_key)
            log.info("Supabase client initialized")
        except Exception as e:
            log.error(f"Failed to initialize Supabase: {e}")
            raise
    return _client


# Convenience alias — import this in other modules
supabase = get_supabase()
