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
)

_logger = logging.getLogger(__name__)

_TRENDS_GEO = "TR"


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
    Builds the weekly "this week in your city" trend report.

    Strategy:
    - One Trending Now call for Turkey (geo="TR") to find category-matched terms.
    - One interest-over-time call per matched term to score it.
    - One backend call per (city, category) combo to fetch matching events.

    This minimises SerpAPI quota usage vs. per-city Trending Now calls,
    which the API does not support well at province level.
    """

    def __init__(
        self,
        trends_client: Optional[SerpApiTrendsClient] = None,
        backend_client: Optional[BackendClient] = None,
    ) -> None:
        self._client = trends_client or SerpApiTrendsClient()
        self._backend = backend_client or BackendClient(base_url=settings.backend_url)

    def build_report(self) -> Dict[str, Any]:
        if not self._client.is_enabled:
            _logger.warning("[WARN] SERPAPI_API_KEY tanimli degil. Trend analizi atlandi.")
            return {"cities": {}, "requestCount": 0}

        # Step 1: single Trending Now call at country level
        try:
            trending_terms = self._client.trending_now(geo=_TRENDS_GEO)
        except RuntimeError as exc:
            _logger.warning("Trending Now sorgusu basarisiz: %s", exc)
            return {"cities": {}, "requestCount": self._client.request_count}

        # Step 2: match trending terms to our event categories
        candidates: List[Dict[str, Any]] = []
        for entry in trending_terms:
            term = (entry.get("query") or entry.get("title") or "").strip()
            if not term:
                continue
            category = _match_category(term)
            if category is None:
                continue
            if any(c["category"] == category for c in candidates):
                # one candidate per category keeps the report focused
                continue
            candidates.append({"term": term, "category": category})
            if len(candidates) >= settings.trends_max_candidates_per_city:
                break

        _logger.info(
            "Trending Now (geo=%s): %s terim bulundu, %s kategoriyle eslestirildi.",
            _TRENDS_GEO, len(trending_terms), len(candidates),
        )

        # Step 3: score each candidate via interest-over-time
        for candidate in candidates:
            candidate["trendScore"] = self._score_candidate(candidate["term"])

        candidates.sort(key=lambda c: c["trendScore"], reverse=True)

        # Step 4: for each city, fetch matching events per candidate category
        cities_report: Dict[str, List[Dict[str, Any]]] = {}
        for city in TREND_CITIES:
            city_candidates = []
            for candidate in candidates:
                events = self._fetch_matching_events(city=city, category=candidate["category"])
                city_candidates.append({**candidate, "events": events})
            cities_report[city] = city_candidates

        return {"cities": cities_report, "requestCount": self._client.request_count}

    def _score_candidate(self, query: str) -> int:
        try:
            timeline = self._client.interest_over_time(
                query=query,
                geo=_TRENDS_GEO,
                lookback_days=settings.trends_lookback_days,
            )
        except RuntimeError as exc:
            _logger.warning("Interest-over-time sorgusu basarisiz query=%s: %s", query, exc)
            return 0

        values: List[int] = []
        for point in timeline:
            for series in point.get("values", []):
                extracted = series.get("extracted_value")
                if isinstance(extracted, int):
                    values.append(extracted)

        return max(values) if values else 0

    def _fetch_matching_events(self, *, city: str, category: str) -> List[Dict[str, Any]]:
        backend_type = TREND_CATEGORY_TO_BACKEND_TYPE.get(category)
        if not backend_type:
            return []
        return self._backend.get_trend_candidates(city=city, category=backend_type, limit=5)
