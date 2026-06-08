from __future__ import annotations

import logging
import unicodedata
from typing import Any, Dict, List, Optional

from clients.backend_client import BackendClient
from clients.serpapi_trends_client import SerpApiTrendsClient
from config import settings
from utils.constants import (
    TREND_CATEGORY_KEYWORDS,
    TREND_CATEGORY_TO_BACKEND_TYPE,
    TREND_CITIES,
    TREND_CITY_GEO,
)

_logger = logging.getLogger(__name__)


_TURKISH_FOLD_MAP = str.maketrans({"ı": "i", "İ": "i"})


def _fold(text: str) -> str:
    """Lowercases and strips Turkish accents for keyword matching (İ/ı->i, ş->s, ...).

    NFKD decomposes ş/ç/ğ/ö/ü into base+combining marks, but the Turkish
    dotless 'ı' (and its uppercase 'İ') have no such decomposition, so they
    are mapped explicitly before the NFKD pass.
    """
    folded = text.translate(_TURKISH_FOLD_MAP).lower()
    normalized = unicodedata.normalize("NFKD", folded)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _match_category(term: str) -> Optional[str]:
    folded_term = _fold(term)
    for category, keywords in TREND_CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if _fold(keyword) in folded_term:
                return category
    return None


class TrendAnalysisService:
    """
    Builds the weekly "this week in your city" trend report:
    for each priority city, finds trending search terms that match one of our
    event categories and ranks them by Google Trends interest score.
    """

    def __init__(
        self,
        trends_client: Optional[SerpApiTrendsClient] = None,
        backend_client: Optional[BackendClient] = None,
    ) -> None:
        self._client = trends_client or SerpApiTrendsClient()
        self._backend = backend_client or BackendClient(base_url=settings.backend_url)

    def build_report(self) -> Dict[str, Any]:
        cities_report: Dict[str, List[Dict[str, Any]]] = {}

        if not self._client.is_enabled:
            _logger.warning("[WARN] SERPAPI_API_KEY tanimli degil. Trend analizi atlandi.")
            return {"cities": cities_report, "requestCount": 0}

        for city in TREND_CITIES:
            geo = TREND_CITY_GEO.get(city)
            if not geo:
                _logger.warning("Trend geo kodu bulunamadi, sehir atlaniyor: %s", city)
                continue
            cities_report[city] = self._build_city_section(city=city, geo=geo)

        return {"cities": cities_report, "requestCount": self._client.request_count}

    def _build_city_section(self, *, city: str, geo: str) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        try:
            trending_terms = self._client.trending_now(geo=geo)
        except RuntimeError as exc:
            _logger.warning("Trending Now sorgusu basarisiz sehir=%s: %s", city, exc)
            return candidates

        for entry in trending_terms:
            term = (entry.get("query") or entry.get("title") or "").strip()
            if not term:
                continue
            category = _match_category(term)
            if category is None:
                continue
            candidates.append({"term": term, "category": category})
            if len(candidates) >= settings.trends_max_candidates_per_city:
                break

        for candidate in candidates:
            candidate["trendScore"] = self._score_candidate(query=candidate["term"], geo=geo)
            candidate["events"] = self._fetch_matching_events(city=city, category=candidate["category"])

        candidates.sort(key=lambda item: item["trendScore"], reverse=True)
        return candidates

    def _fetch_matching_events(self, *, city: str, category: str) -> List[Dict[str, Any]]:
        backend_type = TREND_CATEGORY_TO_BACKEND_TYPE.get(category)
        if not backend_type:
            return []
        return self._backend.get_trend_candidates(city=city, category=backend_type, limit=5)

    def _score_candidate(self, *, query: str, geo: str) -> int:
        try:
            timeline = self._client.interest_over_time(
                query=query,
                geo=geo,
                lookback_days=settings.trends_lookback_days,
            )
        except RuntimeError as exc:
            _logger.warning("Interest-over-time sorgusu basarisiz query=%s: %s", query, exc)
            return 0

        if not timeline:
            return 0

        values: List[int] = []
        for point in timeline:
            for series in point.get("values", []):
                extracted = series.get("extracted_value")
                if isinstance(extracted, int):
                    values.append(extracted)

        return max(values) if values else 0
