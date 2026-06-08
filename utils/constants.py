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

# Priority cities for the weekly trend-analysis feature ("this week in your city"
# Instagram posts), ordered by post priority.
TREND_CITIES: list[str] = [
    "İstanbul",
    "İzmir",
    "Ankara",
    "Bursa",
    "Eskişehir",
    "Antalya",
    "Denizli",
]

# Google Trends region codes (ISO 3166-2:TR province codes) for each priority city.
TREND_CITY_GEO: Dict[str, str] = {
    "İstanbul": "TR-34",
    "İzmir": "TR-35",
    "Ankara": "TR-06",
    "Bursa": "TR-16",
    "Eskişehir": "TR-26",
    "Antalya": "TR-07",
    "Denizli": "TR-20",
}

# Maps our event categories to Turkish keyword sets used to recognize a trending
# search term as belonging to that category (lowercase, accent-folded match).
TREND_CATEGORY_KEYWORDS: Dict[str, list[str]] = {
    "concert": ["konser", "müzik", "muzik", "festival müzik"],
    "theatre": ["tiyatro", "oyun", "sahne"],
    "standup": ["stand up", "stand-up", "komedi"],
    "festival": ["festival"],
    "cinema": ["sinema", "film", "vizyon"],
    "exhibition": ["sergi", "galeri", "müze", "muze"],
    "experience": ["atölye", "atolye", "workshop", "deneyim"],
    "show": ["söyleşi", "soylesi", "panel", "konferans"],
    "sports": ["maç", "mac", "spor", "lig"],
    "family": ["çocuk", "cocuk", "aile"],
}

# Maps the trend service's category buckets (used for matching trending search
# terms) to the canonical category ids stored in Event.Type on the backend
# (see LokalizeBackend Domain/Utilities/CategoryCatalog.cs), so that
# GET /api/events/trend-candidates?category=<id> returns matching events.
TREND_CATEGORY_TO_BACKEND_TYPE: Dict[str, str] = {
    "concert": "concert",
    "theatre": "theatre",
    "standup": "standup",
    "festival": "festival",
    "cinema": "cinema",
    "exhibition": "exhibition",
    "experience": "workshop",
    "show": "festival",
    "sports": "match",
    "family": "kids",
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
