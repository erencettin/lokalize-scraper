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
    "standup": "standup",
    "stand-up": "standup",
    "stand up": "standup",
    "comedy": "standup",
    "music": "concert",
    "concert": "concert",
    "theatre": "theatre",
    "theater": "theatre",
    "arts": "show",
    "family": "kids",
    "sports": "match",
    "film": "cinema",
    "festival": "festival",
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
