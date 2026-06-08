import os
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()

SERPAPI_EVENTS_QUERY_TEMPLATES = [
    {"q": "{city} konser ve müzik etkinlikleri", "category": "concert"},
    {"q": "{city} tiyatro ve sahne sanatları", "category": "theater"},
    {"q": "{city} sinema ve film gösterimleri", "category": "cinema"},
    {"q": "{city} sergi ve sanat etkinlikleri", "category": "art"},
    {"q": "{city} stand-up ve komedi gösterileri", "category": "standup"},
    {"q": "{city} festival ve büyük etkinlikler", "category": "festival"},
    {"q": "{city} spor etkinlikleri", "category": "sports"},
    {"q": "{city} workshop ve eğitim atölyeleri", "category": "workshop"},
    {"q": "{city} yeme içme ve deneyim etkinlikleri", "category": "experience"},
    {"q": "{city} aile ve çocuk etkinlikleri", "category": "family"},
]

class Settings(BaseSettings):
    backend_url: str = Field("", alias="BACKEND_URL")
    
    # Sync Config
    sync_mode: str = Field("live", alias="SYNC_MODE")  # live | dry_run
    deactivate_stale_days: int = 7
    
    # Scraper Tuning
    headless: bool = True
    timeout: int = 30000  # ms

    # Ticketmaster Provider Config
    ticketmaster_api_key: str = Field("", alias="TICKETMASTER_API_KEY")
    ticketmaster_enabled: bool = Field(False, alias="TICKETMASTER_ENABLED")
    ticketmaster_user_agent: str = Field("LokalizeApp/1.0", alias="TICKETMASTER_USER_AGENT")
    ticketmaster_country_code: str = Field("TR", alias="TICKETMASTER_COUNTRY_CODE")
    ticketmaster_size: int = Field(200, alias="TICKETMASTER_SIZE")      # Discovery API max per page
    ticketmaster_max_pages: int = Field(0, alias="TICKETMASTER_MAX_PAGES")  # 0 = no artificial cap
    ticketmaster_page_delay_seconds: float = Field(1.0, alias="TICKETMASTER_PAGE_DELAY_SECONDS")
    ticketmaster_timeout_seconds: int = Field(20, alias="TICKETMASTER_TIMEOUT_SECONDS")
    ticketmaster_max_retries: int = Field(3, alias="TICKETMASTER_MAX_RETRIES")
    ticketmaster_detail_price_enabled: bool = Field(False, alias="TICKETMASTER_DETAIL_PRICE_ENABLED")
    ticketmaster_detail_price_limit: int = Field(0, alias="TICKETMASTER_DETAIL_PRICE_LIMIT")
    ticketmaster_detail_price_timeout_seconds: int = Field(15, alias="TICKETMASTER_DETAIL_PRICE_TIMEOUT_SECONDS")
    ticketmaster_detail_price_max_retries: int = Field(2, alias="TICKETMASTER_DETAIL_PRICE_MAX_RETRIES")
    ticketmaster_lookahead_days: int = Field(120, alias="TICKETMASTER_LOOKAHEAD_DAYS")

    # Biletix detail page enrichment ("Etkinliğe Dair" scraping — permission granted by Biletix 2026-06-08)
    biletix_detail_enabled: bool = Field(True, alias="BILETIX_DETAIL_ENABLED")
    biletix_detail_user_agent: str = Field(
        "LokalizeAppBot/1.0 (contact: iletisim.lokalizeapp@gmail.com)",
        alias="BILETIX_DETAIL_USER_AGENT",
    )
    biletix_detail_timeout_seconds: int = Field(15, alias="BILETIX_DETAIL_TIMEOUT_SECONDS")
    biletix_detail_max_retries: int = Field(2, alias="BILETIX_DETAIL_MAX_RETRIES")

    # Municipal Open Data / RSS Provider Config
    municipal_rss_enabled: bool = Field(False, alias="MUNICIPAL_RSS_ENABLED")
    municipal_rss_urls: str = Field("", alias="MUNICIPAL_RSS_URLS")
    municipal_rss_city_name: str = Field("Istanbul", alias="MUNICIPAL_RSS_CITY_NAME")
    municipal_rss_timeout_seconds: int = Field(20, alias="MUNICIPAL_RSS_TIMEOUT_SECONDS")
    municipal_rss_max_retries: int = Field(3, alias="MUNICIPAL_RSS_MAX_RETRIES")
    municipal_rss_lookahead_days: int = Field(120, alias="MUNICIPAL_RSS_LOOKAHEAD_DAYS")

    # Municipal Web Provider Config
    municipal_web_enabled: bool = Field(False, alias="MUNICIPAL_WEB_ENABLED")
    municipal_web_city_name: str = Field("Istanbul", alias="MUNICIPAL_WEB_CITY_NAME")
    municipal_web_user_agent: str = Field(
        "LokalizeAppBot/1.0 (contact: iletisim.lokalizeapp@gmail.com)",
        alias="MUNICIPAL_WEB_USER_AGENT",
    )
    municipal_web_timeout_seconds: int = Field(20, alias="MUNICIPAL_WEB_TIMEOUT_SECONDS")
    municipal_web_max_retries: int = Field(3, alias="MUNICIPAL_WEB_MAX_RETRIES")
    municipal_web_lookahead_days: int = Field(120, alias="MUNICIPAL_WEB_LOOKAHEAD_DAYS")
    municipal_web_max_items_per_site: int = Field(20, alias="MUNICIPAL_WEB_MAX_ITEMS_PER_SITE")
    municipal_web_list_delay_seconds: float = Field(1.5, alias="MUNICIPAL_WEB_LIST_DELAY_SECONDS")
    municipal_web_detail_delay_seconds: float = Field(1.2, alias="MUNICIPAL_WEB_DETAIL_DELAY_SECONDS")

    # biletimGO Provider Config
    biletimgo_access_token: str = Field("", alias="BILETIMGO_ACCESS_TOKEN")
    biletimgo_enabled: bool = Field(False, alias="BILETIMGO_ENABLED")
    biletimgo_timeout_seconds: int = Field(20, alias="BILETIMGO_TIMEOUT_SECONDS")

    # Bilet.com Affiliate API Config
    biletcom_enabled: bool = Field(False, alias="BILETCOM_ENABLED")
    biletcom_client_id: str = Field("", alias="BILETCOM_CLIENT_ID")
    biletcom_client_secret: str = Field("", alias="BILETCOM_CLIENT_SECRET")
    biletcom_timeout_seconds: int = Field(20, alias="BILETCOM_TIMEOUT_SECONDS")
    biletcom_detail_workers: int = Field(5, alias="BILETCOM_DETAIL_WORKERS")
    biletcom_lookahead_days: int = Field(120, alias="BILETCOM_LOOKAHEAD_DAYS")

    # SerpAPI Nearby Config
    serpapi_api_key: str = Field("", alias="SERPAPI_API_KEY")
    serpapi_city: str = Field("Istanbul", alias="SERPAPI_CITY")
    serpapi_timeout_seconds: int = Field(30, alias="SERPAPI_TIMEOUT_SECONDS")
    serpapi_max_attempts: int = Field(2, alias="SERPAPI_MAX_ATTEMPTS")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

settings = Settings()




def build_serpapi_events_queries(city: str):
    resolved_city = (city or settings.serpapi_city).strip()
    return [
        {"q": item["q"].format(city=resolved_city), "category": item["category"]}
        for item in SERPAPI_EVENTS_QUERY_TEMPLATES
    ]
