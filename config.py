import os
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    supabase_url: str = Field(..., alias="SUPABASE_URL")
    supabase_key: str = Field(..., alias="SUPABASE_SERVICE_ROLE_KEY")
    
    # Sync Config
    sync_mode: str = Field("live", alias="SYNC_MODE")  # live | dry_run
    deactivate_stale_days: int = 7
    
    # Scraper Tuning
    headless: bool = True
    timeout: int = 30000  # ms

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
