import os
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    supabase_url: str = Field("https://your-project.supabase.co", alias="SUPABASE_URL")
    supabase_key: str = Field("your-service-role-key", alias="SUPABASE_SERVICE_ROLE_KEY")
    
    # Sync Config
    sync_mode: str = Field("live", alias="SYNC_MODE")  # live | dry_run
    deactivate_stale_days: int = 7
    
    # Scraper Tuning
    headless: bool = True
    timeout: int = 30000  # ms

    # Ticketmaster Provider Config
    ticketmaster_api_key: str = Field("", alias="TICKETMASTER_API_KEY")
    ticketmaster_enabled: bool = Field(False, alias="TICKETMASTER_ENABLED")
    ticketmaster_country_code: str = Field("TR", alias="TICKETMASTER_COUNTRY_CODE")
    ticketmaster_city: str = Field("Istanbul", alias="TICKETMASTER_CITY")
    ticketmaster_size: int = Field(50, alias="TICKETMASTER_SIZE")
    ticketmaster_max_pages: int = Field(3, alias="TICKETMASTER_MAX_PAGES")
    ticketmaster_timeout_seconds: int = Field(20, alias="TICKETMASTER_TIMEOUT_SECONDS")
    ticketmaster_max_retries: int = Field(3, alias="TICKETMASTER_MAX_RETRIES")

    # PredictHQ Provider Config
    predicthq_access_token: str = Field("", alias="PREDICTHQ_ACCESS_TOKEN")
    predicthq_enabled: bool = Field(False, alias="PREDICTHQ_ENABLED")
    predicthq_query: str = Field("istanbul", alias="PREDICTHQ_QUERY")
    predicthq_country: str = Field("TR", alias="PREDICTHQ_COUNTRY")
    predicthq_limit: int = Field(50, alias="PREDICTHQ_LIMIT")
    predicthq_max_pages: int = Field(3, alias="PREDICTHQ_MAX_PAGES")
    predicthq_timeout_seconds: int = Field(20, alias="PREDICTHQ_TIMEOUT_SECONDS")
    predicthq_max_retries: int = Field(3, alias="PREDICTHQ_MAX_RETRIES")

    # Municipal Open Data / RSS Provider Config
    municipal_rss_enabled: bool = Field(False, alias="MUNICIPAL_RSS_ENABLED")
    municipal_rss_urls: str = Field("", alias="MUNICIPAL_RSS_URLS")
    municipal_rss_city_name: str = Field("Istanbul", alias="MUNICIPAL_RSS_CITY_NAME")
    municipal_rss_timeout_seconds: int = Field(20, alias="MUNICIPAL_RSS_TIMEOUT_SECONDS")
    municipal_rss_max_retries: int = Field(3, alias="MUNICIPAL_RSS_MAX_RETRIES")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

settings = Settings()
