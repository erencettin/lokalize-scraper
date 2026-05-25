"""Shared constants reused by multiple providers."""

from typing import Dict

TURKISH_MONTHS: Dict[str, int] = {
    "ocak": 1,
    "subat": 2,
    "şubat": 2,
    "mart": 3,
    "nisan": 4,
    "mayis": 5,
    "mayıs": 5,
    "haziran": 6,
    "temmuz": 7,
    "agustos": 8,
    "ağustos": 8,
    "eylul": 9,
    "eylül": 9,
    "ekim": 10,
    "kasim": 11,
    "kasım": 11,
    "aralik": 12,
    "aralık": 12,
    "şub": 2,
    "ağu": 8,
    "eyl": 9,
    "ara": 12,
    "oca": 1,
    "nis": 4,
    "may": 5,
    "haz": 6,
    "tem": 7,
    "agu": 8,
    "eki": 10,
    "kas": 11,
}

CATEGORY_MAP: Dict[str, str] = {
    "konser": "concert",
    "muzik": "concert",
    "müzik": "concert",
    "tiyatro": "theatre",
    "stand up": "standup",
    "stand-up": "standup",
    "komedi": "standup",
    "festival": "festival",
    "sinema": "cinema",
    "film": "cinema",
    "sergi": "exhibition",
    "atolye": "experience",
    "atölye": "experience",
    "workshop": "experience",
    "etkinlik": "experience",
    "söyleşi": "show",
    "panel": "show",
    "konferans": "show",
}

CANONICAL_PROVIDER_ORDER: list[str] = [
    "Ticketmaster",
    "MunicipalRSS",
    "MunicipalWeb",
    "SerpAPIEvents",
    "SerpAPILocal",
    "BiletimGO",
]

CANONICAL_PROVIDER_ALIASES: Dict[str, str] = {
    "ticketmaster": "Ticketmaster",
    "municipalrss": "MunicipalRSS",
    "municipal_rss": "MunicipalRSS",
    "municipalweb": "MunicipalWeb",
    "municipal_web": "MunicipalWeb",
    "serpapievents": "SerpAPIEvents",
    "serpapi_events": "SerpAPIEvents",
    "serpapi_google_events": "SerpAPIEvents",
    "serpapilocal": "SerpAPILocal",
    "serpapi_local": "SerpAPILocal",
    "serpapi_google_local": "SerpAPILocal",
    "biletimgo": "BiletimGO",
    "biletimgo_partner": "BiletimGO",
}

PROVIDER_UI_TAG_MAP: Dict[str, str] = {
    "Ticketmaster": "Ticketmaster",
    "MunicipalRSS": "İBB",
    "SerpAPIEvents": "Google",
    "SerpAPILocal": "Google",
    "BiletimGO": "biletimGO",
}
