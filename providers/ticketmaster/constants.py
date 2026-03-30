"""Ticketmaster provider constants."""

from __future__ import annotations

BASE_URL = "https://app.ticketmaster.com/discovery/v2/"
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
    "family": "show",
    "sports": "match",
    "film": "cinema",
    "festival": "festival",
    "miscellaneous": "experience",
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
