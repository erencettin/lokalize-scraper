"""Constants for municipal RSS provider."""

from typing import Set

from utils.constants import CATEGORY_MAP, TURKISH_MONTHS

ISTANBUL_TIMEZONE = "Europe/Istanbul"
DEFAULT_VENUE = "Resmi Belediye Etkinlik Kaynagi"
DEFAULT_CITY_NAME = "Istanbul"

MAX_DESCRIPTION_LENGTH = 250
EXTERNAL_ID_PREFIX = "rss"
EXTERNAL_ID_HASH_LENGTH = 16

FEED_DELAY_SECONDS = 1.5
WP_EVENT_PER_PAGE = 50
WP_POST_PER_PAGE = 30
CONTENT_SEARCH_WINDOW = 600
TIME_SEARCH_WINDOW = 120

DEFAULT_ACCEPT_HEADER = "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8"
DEFAULT_USER_AGENT = "LokalizeAppBot/1.0 (contact: iletisim.lokalizeapp@gmail.com)"

RETRYABLE_STATUS_CODES: Set[int] = {429, 500, 502, 503, 504}

PARSER_RSS_XML = "rss_xml"
PARSER_WORDPRESS = "wordpress"
PARSER_KULTURSANAT = "kultursanat"
PARSER_ATATURK_KITAPLIGI = "ataturk_kitapligi"

WORDPRESS_EVENT_KEYS = (
    "event_start_datetime",
    "event_start_date_time",
    "event_start",
    "start_datetime",
    "start_date_time",
    "start_at",
    "event_start_at",
)
WORDPRESS_DATE_KEYS = ("event_start_date", "event_date", "start_date", "startDate", "eventStartDate")
WORDPRESS_TIME_KEYS = ("event_start_time", "start_time", "startTime", "eventStartTime", "time")
WORDPRESS_VENUE_KEYS = ("venue", "venue_name", "event_venue", "location", "place", "event_place")
WORDPRESS_TEXT_DATE_PATTERNS = (
    r"(\d{1,2}\s+[A-Za-zÇĞİÖŞÜçğıöşü]+\s+\d{4}\s+\d{2}:\d{2})",
    r"(\d{1,2}\s+[A-Za-zÇĞİÖŞÜçğıöşü]+\s+\d{4})",
    r"(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})",
    r"(\d{2}\.\d{2}\.\d{4})",
)
