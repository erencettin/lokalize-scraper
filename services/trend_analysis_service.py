from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from clients.backend_client import BackendClient
from clients.serpapi_trends_client import SerpApiTrendsClient
from config import settings
from utils.constants import TREND_CATEGORIES, TREND_CITIES

_logger = logging.getLogger(__name__)

_TRENDS_GEO = "TR"


def _normalize(text: str) -> str:
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosucgiosu")
    return text.lower().translate(tr_map)


class TrendAnalysisService:
    """
    Builds the weekly "this week in your city" trend report.

    Strategy:
    - One related-queries call per category (12 total) to discover which specific
      events/artists are trending in Turkey for that category.
    - One backend call per (city × category) to fetch candidate events.
    - Events are matched against trending terms via fuzzy word overlap.
    - Only events with at least one match are included in the report.

    Total SerpAPI budget: 12 requests/week, same as before.
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

        week_from, week_to = self._compute_week_range()
        _logger.info("Haftalık tarama aralığı: %s – %s", week_from, week_to)

        # Step 1: get trending related queries per category (one SerpAPI call each)
        category_terms: Dict[str, List[str]] = {}
        for cat in TREND_CATEGORIES:
            terms = self._get_related_terms(cat["query"])
            category_terms[cat["id"]] = terms
            _logger.info(
                "Kategori '%s' için %d trending terim: %s",
                cat["label"], len(terms), terms[:5],
            )

        # Step 2: for each city, match trending terms against backend events
        cities_report: Dict[str, List[Dict[str, Any]]] = {}
        for city in TREND_CITIES:
            city_candidates = []
            for cat in TREND_CATEGORIES:
                terms = category_terms[cat["id"]]
                events = self._fetch_and_match(
                    city=city,
                    backend_type=cat["backendType"],
                    terms=terms,
                    date_from=week_from,
                    date_to=week_to,
                )
                city_candidates.append({
                    "category":     cat["id"],
                    "label":        cat["label"],
                    "trendingTerms": terms[:10],
                    "events":       events,
                })
            cities_report[city] = city_candidates

        return {"cities": cities_report, "requestCount": self._client.request_count}

    def _get_related_terms(self, query: str) -> List[str]:
        try:
            related = self._client.related_queries(
                query=query,
                geo=_TRENDS_GEO,
                lookback_days=settings.trends_lookback_days,
            )
        except RuntimeError as exc:
            _logger.warning("Related queries başarısız query=%s: %s", query, exc)
            return []

        terms: List[str] = []
        for section in ("rising", "top"):
            for item in related.get(section) or []:
                q = item.get("query", "").strip()
                if q and q not in terms:
                    terms.append(q)
        return terms

    def _fetch_and_match(
        self,
        *,
        city: str,
        backend_type: str,
        terms: List[str],
        date_from: date,
        date_to: date,
    ) -> List[Dict[str, Any]]:
        if not terms:
            return []

        raw = self._backend.get_trend_candidates(city=city, category=backend_type, limit=50)

        scored: List[tuple[int, Dict[str, Any]]] = []
        for event in raw:
            if not self._in_week(event, date_from, date_to):
                continue
            score = self._match_score(event.get("title", ""), terms)
            if score > 0:
                scored.append((score, event))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:5]]

    @staticmethod
    def _compute_week_range() -> tuple[date, date]:
        today = date.today()
        days_until_monday = (7 - today.weekday()) % 7 or 7
        next_monday = today + timedelta(days=days_until_monday)
        return next_monday, next_monday + timedelta(days=6)

    @staticmethod
    def _in_week(event: Dict[str, Any], date_from: date, date_to: date) -> bool:
        raw = event.get("nextDate")
        if not raw:
            return True
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            d = dt.date()
            return d.year >= 2050 or date_from <= d <= date_to
        except Exception:
            return True

    @staticmethod
    def _match_score(title: str, terms: List[str]) -> int:
        title_words = set(w for w in _normalize(title).split() if len(w) > 2)
        score = 0
        for term in terms:
            term_words = set(w for w in _normalize(term).split() if len(w) > 2)
            score += len(term_words & title_words)
        return score
