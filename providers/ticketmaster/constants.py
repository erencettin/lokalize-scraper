"""Ticketmaster provider constants."""

from __future__ import annotations

FEED_BASE_URL = "https://app.ticketmaster.com/discovery-feed/v2/"
BASE_URL = "https://app.ticketmaster.com/discovery/v2/"
AFFILIATE_URL_PREFIX = "ticketmaster.evyy.net/c/"
# Impact Radius deep link — used for events where the Discovery Feed omits primaryEventUrl.
# ircid=23908 is the Ticketmaster/Biletix campaign ID extracted from working affiliate URLs.
AFFILIATE_DEEP_LINK_TEMPLATE = "https://ticketmaster.evyy.net/c/7294156/23908?u={encoded_url}"
EVENTS_ENDPOINT = "events.json"
DETAIL_ENDPOINT_TEMPLATE = "events/{event_id}.json"
ISTANBUL_TIMEZONE = "Europe/Istanbul"

TICKETMASTER_CATEGORY_MAP = {
    # English (Ticketmaster international)
    "standup": "standup",
    "stand-up": "standup",
    "stand up": "standup",
    "comedy": "standup",
    "music": "concert",
    "concert": "concert",
    "theatre": "theatre",
    "theater": "theatre",
    "arts": "theatre",
    "arts & theatre": "theatre",
    "performing arts": "theatre",
    "family": "kids",
    "sports": "match",
    "film": "cinema",
    "festival": "festival",
    "exhibition": "exhibition",
    "workshop": "workshop",
    # Turkish (Biletix Turkey)
    "muzik": "concert",
    "müzik": "concert",
    "spor": "match",
    "sahne": "theatre",
    "aile": "kids",
    "egitim": "workshop",
    "eğitim": "workshop",
    "eğitim & fazlası": "workshop",
    "egitim & fazlasi": "workshop",
    "sergi": "exhibition",
    "tiyatro": "theatre",
    # Miscellaneous segment — covers Biletix "Eğitim & Fazlası" and uncategorised events
    "miscellaneous": "social",
}

DEFAULT_USER_AGENT = "LokalizeApp/1.0"
DEFAULT_EVENT_TYPE = "show"
DEFAULT_VENUE_NAME = "Mekan bilgisi yok"
DEFAULT_PRICE_TEXT = "Fiyat bilgisi yok"
FREE_PRICE_TEXT = "Ucretsiz"
DEFAULT_TICKET_STATUS = "on_sale"
DEFAULT_CURRENCY = "TRY"

MAX_DESCRIPTION_LENGTH = 2000
ERROR_PREVIEW_LENGTH = 300
DETAIL_PREVIEW_LENGTH = 200

RETRYABLE_STATUS_CODES = {429}
AUTH_FAILURE_STATUS_CODES = {401, 403}

# Rate limiting: minimum interval between requests to stay under 100 req/min OAuth limit.
# 0.65s → ~92 req/min, gives ~8% headroom below the 100 req/min cap.
RATE_LIMIT_MIN_INTERVAL_SECONDS = 0.65
# Maximum backoff cap (seconds) for exponential retry delays.
MAX_RETRY_BACKOFF_SECONDS = 60
# Default sort order for paginated event queries.
DEFAULT_SORT = "date,asc"
