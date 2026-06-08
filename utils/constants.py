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
# All frontend-visible categories, mapped to backend canonical Event.Type values
# (see LokalizeBackend Domain/Utilities/CategoryCatalog.cs).
# Order here determines the display order in the Markdown report.
TREND_CATEGORIES: list[Dict[str, str]] = [
    {"id": "concert",   "label": "🎵 Konser & Müzik",       "backendType": "concert",   "query": "konser"},
    {"id": "theatre",   "label": "🎭 Tiyatro & Sahne",       "backendType": "theatre",   "query": "tiyatro"},
    {"id": "cinema",    "label": "🎬 Sinema & Gösterim",     "backendType": "cinema",    "query": "sinema vizyonda"},
    {"id": "activity",  "label": "🎡 Aktivite & Deneyim",   "backendType": "activity",  "query": "aktivite etkinlik"},
    {"id": "exhibition","label": "🖼️ Sergi & Sanat",        "backendType": "exhibition","query": "sergi sanat"},
    {"id": "standup",   "label": "🎤 Stand-up & Gösteri",   "backendType": "standup",   "query": "stand up komedi"},
    {"id": "festival",  "label": "🎪 Festival & Gösteri",   "backendType": "festival",  "query": "festival etkinlik"},
    {"id": "sports",    "label": "⚽ Spor Etkinlikleri",    "backendType": "match",     "query": "spor etkinlik bilet"},
    {"id": "workshop",  "label": "📚 Workshop & Eğitim",    "backendType": "workshop",  "query": "atölye workshop"},
    {"id": "food",      "label": "🍽️ Yeme & İçme",         "backendType": "food",      "query": "yeme içme etkinlik"},
    {"id": "kids",      "label": "👨‍👩‍👧 Aile & Çocuk",      "backendType": "kids",      "query": "çocuk aile etkinlik"},
    {"id": "social",    "label": "🎉 Sosyal & Eğlence",     "backendType": "social",    "query": "sosyal etkinlik"},
]

# Legacy mapping kept for backwards-compat with any existing references.
TREND_CATEGORY_TO_BACKEND_TYPE: Dict[str, str] = {
    c["id"]: c["backendType"] for c in TREND_CATEGORIES
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
