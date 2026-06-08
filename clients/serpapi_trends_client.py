from __future__ import annotations

from typing import Any, Dict, List, Optional

from clients.serpapi_client import SerpApiClient


class SerpApiTrendsClient:
    """Thin wrapper around SerpApiClient for the Google Trends family of engines."""

    def __init__(self, client: Optional[SerpApiClient] = None) -> None:
        self._client = client or SerpApiClient()

    @property
    def is_enabled(self) -> bool:
        return self._client.is_enabled

    @property
    def request_count(self) -> int:
        return self._client.request_count

    def trending_now(self, *, geo: str) -> List[Dict[str, Any]]:
        """Returns currently trending search terms for a region (e.g. geo='TR-34' for İstanbul)."""
        payload = self._client.search(
            engine="google_trends_trending_now",
            extra_params={"geo": geo},
        )
        return payload.get("trending_searches", []) or []

    def interest_over_time(self, *, query: str, geo: str, lookback_days: int = 14) -> List[Dict[str, Any]]:
        """Returns the interest-over-time series for a query in a region over the last N days."""
        date_range = "now 7-d" if lookback_days <= 7 else "today 1-m"
        payload = self._client.search(
            engine="google_trends",
            query=query,
            extra_params={"geo": geo, "data_type": "TIMESERIES", "date": date_range},
        )
        timeline = payload.get("interest_over_time", {}).get("timeline_data", [])
        return timeline or []

    def google_events(self, *, query: str) -> List[Dict[str, Any]]:
        """Returns upcoming events from Google Events for a search query."""
        payload = self._client.search(
            engine="google_events",
            query=query,
        )
        return payload.get("events_results", []) or []

    def related_topics(self, *, query: str, geo: str, lookback_days: int = 14) -> Dict[str, Any]:
        """Returns related topics (top + rising Knowledge Graph entities) for a keyword in a region."""
        date_range = "now 7-d" if lookback_days <= 7 else "today 1-m"
        payload = self._client.search(
            engine="google_trends",
            query=query,
            extra_params={"geo": geo, "data_type": "RELATED_TOPICS", "date": date_range},
        )
        return payload.get("related_topics", {})
