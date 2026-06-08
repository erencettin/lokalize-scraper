from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from clients.backend_client import BackendClient
from clients.serpapi_trends_client import SerpApiTrendsClient
from config import settings
from utils.constants import TREND_CATEGORIES, TREND_CITIES

_logger = logging.getLogger(__name__)

# These 4 categories use google_events (28 requests/week).
# Remaining categories fall back to top upcoming events from the DB.
_GOOGLE_EVENTS_CATEGORIES: Dict[str, str] = {
    "concert":  "konser",
    "theatre":  "tiyatro",
    "standup":  "stand up",
    "festival": "festival",
}


def _normalize(text: str) -> str:
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosucgiosu")
    return text.lower().translate(tr_map)


class TrendAnalysisService:
    """
    Builds the weekly "this week in your city" trend report.

    Strategy:
    - For Konser, Tiyatro, Stand-up, Festival: one google_events call per
      (city × category) to fetch what Google actually shows for that search.
      Event titles from Google are matched against our DB events.
      (4 categories × 7 cities = 28 SerpAPI requests/week)
    - For all other categories: top upcoming events from the DB (no API call).
    - If no Google Events match is found for a category, falls back to top
      upcoming DB events so every category always appears in the report.
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

        cities_report: Dict[str, List[Dict[str, Any]]] = {}
        for city in TREND_CITIES:
            city_candidates = []
            for cat in TREND_CATEGORIES:
                term = _GOOGLE_EVENTS_CATEGORIES.get(cat["id"])
                if term:
                    events, is_trending, matched_titles = self._fetch_via_google_events(
                        city=city,
                        backend_type=cat["backendType"],
                        query=f"{city} {term}",
                        date_from=week_from,
                        date_to=week_to,
                    )
                else:
                    events = self._fetch_fallback(
                        city=city,
                        backend_type=cat["backendType"],
                        date_from=week_from,
                        date_to=week_to,
                    )
                    is_trending = False
                    matched_titles = []

                city_candidates.append({
                    "category":      cat["id"],
                    "label":         cat["label"],
                    "trendingTopics": matched_titles,
                    "isTrending":    is_trending,
                    "events":        events,
                })
            cities_report[city] = city_candidates

        return {"cities": cities_report, "requestCount": self._client.request_count}

    def _fetch_via_google_events(
        self,
        *,
        city: str,
        backend_type: str,
        query: str,
        date_from: date,
        date_to: date,
    ) -> tuple[List[Dict[str, Any]], bool, List[str]]:
        # Fetch Google Events titles for this city+category
        google_titles: List[str] = []
        try:
            results = self._client.google_events(query=query)
            google_titles = [r.get("title", "").strip() for r in results if r.get("title")]
            _logger.info("google_events '%s' → %d sonuç: %s", query, len(google_titles), google_titles[:3])
        except RuntimeError as exc:
            _logger.warning("google_events başarısız query=%s: %s", query, exc)

        # Fetch DB candidates and filter by week
        raw = self._backend.get_trend_candidates(city=city, category=backend_type, limit=50)
        in_week = [e for e in raw if self._in_week(e, date_from, date_to)]

        # Match DB events against Google Events titles
        if google_titles:
            scored = []
            for event in in_week:
                score = self._match_score(event.get("title", ""), google_titles)
                if score > 0:
                    scored.append((score, event))
            if scored:
                scored.sort(key=lambda x: x[0], reverse=True)
                matched_events = [e for _, e in scored[:5]]
                matched = self._matched_titles(
                    [e.get("title", "") for e in matched_events],
                    google_titles,
                )
                return matched_events, True, matched

        # Fallback: top upcoming DB events
        return in_week[:5], False, []

    def _fetch_fallback(
        self,
        *,
        city: str,
        backend_type: str,
        date_from: date,
        date_to: date,
    ) -> List[Dict[str, Any]]:
        raw = self._backend.get_trend_candidates(city=city, category=backend_type, limit=20)
        in_week = [e for e in raw if self._in_week(e, date_from, date_to)]
        return in_week[:5]

    @staticmethod
    def _matched_titles(event_titles: List[str], google_titles: List[str]) -> List[str]:
        all_words = set()
        for t in event_titles:
            all_words.update(w for w in _normalize(t).split() if len(w) > 2)
        result = []
        for gt in google_titles:
            gt_words = set(w for w in _normalize(gt).split() if len(w) > 2)
            if gt_words & all_words:
                result.append(gt)
        return result[:5]

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
    def _match_score(db_title: str, google_titles: List[str]) -> int:
        db_words = set(w for w in _normalize(db_title).split() if len(w) > 2)
        score = 0
        for gt in google_titles:
            gt_words = set(w for w in _normalize(gt).split() if len(w) > 2)
            score += len(gt_words & db_words)
        return score
