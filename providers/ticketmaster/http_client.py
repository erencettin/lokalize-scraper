"""HTTP client for Ticketmaster API fetch and retry behavior."""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Set

import requests

from config import settings
from providers.base_http_client import BaseHttpClient
from providers.ticketmaster.constants import AUTH_FAILURE_STATUS_CODES, BASE_URL, DEFAULT_SORT, DEFAULT_USER_AGENT, DETAIL_ENDPOINT_TEMPLATE, DETAIL_PREVIEW_LENGTH, ERROR_PREVIEW_LENGTH, EVENTS_ENDPOINT, MAX_RETRY_BACKOFF_SECONDS, RATE_LIMIT_MIN_INTERVAL_SECONDS, RETRYABLE_STATUS_CODES

class TicketmasterHttpClient(BaseHttpClient):
    """Encapsulates session lifecycle, pagination and request retry logic."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self._local = threading.local()
        self._lock = threading.Lock()
        self._last_request_time = 0.0
        self.last_fetched_pages = 0

    def _get_session(self) -> requests.Session:
        if not hasattr(self._local, "session"):
            session = requests.Session()
            session.headers.update(
                {
                    "User-Agent": settings.ticketmaster_user_agent.strip() or DEFAULT_USER_AGENT,
                    "Accept": "application/json",
                    "Accept-Language": "tr-TR,tr;q=0.9",
                }
            )
            self._local.session = session
        return self._local.session

    def setup_session(self) -> None:
        """Initialize requests session for the main thread."""
        self._get_session()
        self.last_fetched_pages = 0

    def close_session(self) -> None:
        """Close active session and log cleanup errors."""
        try:
            if hasattr(self._local, "session"):
                self._local.session.close()
                del self._local.session
        except Exception as exc:
            self._logger.warning("Ticketmaster: session close failed reason=%s", self._safe_error(exc))

    # Each entry: (label, api_param_key, api_param_value)
    # segmentId is preferred — stable across locales, unlike classificationName string matching.
    # Miscellaneous uses classificationName because its segment ID is not in public Discovery docs.
    # E-Sports uses classificationName at genre level to catch events not attached to a segment.
    # None entry = catch-all (no filter) for unclassified events; stops naturally on empty page or 400.
    BILETIX_QUERIES: list = [
        ("Music",           "segmentId",          "KZFzniwnSyZfZ7v7nJ"),
        ("Arts & Theatre",  "segmentId",          "KZFzniwnSyZfZ7v7na"),
        ("Sports",          "segmentId",          "KZFzniwnSyZfZ7v7nE"),
        ("Family",          "segmentId",          "KZFzniwnSyZfZ7v7n1"),
        ("Miscellaneous",   "classificationName",  "Miscellaneous"),
        ("E-Sports",        "classificationName",  "E-Sports"),
        (None,              None,                  None),
    ]

    def fetch_all_pages(self) -> List[Dict[str, Any]]:
        """Fetch all events by querying each Biletix segment/genre query separately."""
        seen_ids: Set[str] = set()
        all_events: List[Dict[str, Any]] = []
        total_pages_fetched = 0

        for label, param_key, param_value in self.BILETIX_QUERIES:
            segment_events, pages = self._fetch_segment(label, param_key, param_value, seen_ids)
            all_events.extend(segment_events)
            total_pages_fetched += pages
            self._logger.info(
                "Ticketmaster: segment=%r pages=%s events=%s total_so_far=%s",
                label, pages, len(segment_events), len(all_events),
            )

        self.last_fetched_pages = total_pages_fetched
        self._logger.info("Ticketmaster: all segments done total_pages=%s unique_events=%s", total_pages_fetched, len(all_events))
        return all_events

    def _fetch_segment(
        self,
        label: Optional[str],
        param_key: Optional[str],
        param_value: Optional[str],
        seen_ids: Set[str],
    ) -> tuple[List[Dict[str, Any]], int]:
        """Fetch all pages for a single classification query (segment ID, name, or genre)."""
        events: List[Dict[str, Any]] = []
        page = 0
        total_pages: Optional[int] = None

        while True:
            payload = self.fetch_page(page, param_key=param_key, param_value=param_value)
            if payload is None:
                # 400 on deep unfiltered pages is expected; treated as end-of-results.
                self._logger.warning("Ticketmaster: segment=%r page=%s returned None, stopping segment", label, page)
                break

            raw_events, tp = self._parser_extract_page(payload)
            if total_pages is None and tp is not None:
                total_pages = tp

            if not raw_events:
                break

            for item in raw_events:
                if not isinstance(item, dict):
                    continue
                event_id = str(item.get("eventId") or item.get("id") or "")
                if event_id and event_id not in seen_ids:
                    seen_ids.add(event_id)
                    events.append(item)

            page += 1

            if total_pages is not None and page >= total_pages:
                break

            max_pages = settings.ticketmaster_max_pages
            if max_pages > 0 and page >= max_pages:
                break

            time.sleep(settings.ticketmaster_page_delay_seconds)

        return events, page

    def _parser_extract_page(self, payload: Dict[str, Any]):
        """Extract event list and total page count from a Discovery API response."""
        embedded = payload.get("_embedded") or {}
        raw_events = embedded.get("events") if isinstance(embedded, dict) else []
        page_info = payload.get("page") or {}
        total_pages = page_info.get("totalPages") if isinstance(page_info, dict) else None
        if not isinstance(raw_events, list):
            raw_events = []
        return raw_events, total_pages

    def fetch_page(
        self,
        page: int,
        classification_name: Optional[str] = None,
        param_key: Optional[str] = None,
        param_value: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch one page from the Discovery API with an optional classification filter.

        Callers should prefer param_key/param_value (e.g. segmentId=KZFzniwnSyZfZ7v7nJ).
        classification_name is kept for backward compatibility with existing tests.
        """
        params: Dict[str, Any] = {
            "apikey": settings.ticketmaster_api_key,
            "countryCode": settings.ticketmaster_country_code,
            "size": max(settings.ticketmaster_size, 1),
            "page": page,
            "sort": DEFAULT_SORT,
        }
        effective_key = param_key or ("classificationName" if classification_name else None)
        effective_value = param_value or classification_name
        if effective_key and effective_value:
            params[effective_key] = effective_value
            params["locale"] = "tr,*"
        response = self._request_with_retry(
            f"{BASE_URL}{EVENTS_ENDPOINT}",
            params,
            max(settings.ticketmaster_timeout_seconds, 1),
            max(settings.ticketmaster_max_retries, 1),
        )
        if response is None or response.status_code != 200:
            self._logger.warning(
                "Ticketmaster: page %s %s=%r failed status=%s",
                page,
                effective_key or "unfiltered",
                effective_value,
                getattr(response, "status_code", "none"),
            )
            return None
        return self._parse_json(response, "page", page)

    def fetch_event_detail(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Fetch event detail payload used for optional price fallback."""
        url = f"{BASE_URL}{DETAIL_ENDPOINT_TEMPLATE.format(event_id=event_id)}"
        params = {"apikey": settings.ticketmaster_api_key, "include": "priceRanges"}
        response = self._request_with_retry(url, params, max(settings.ticketmaster_detail_price_timeout_seconds, 1), max(settings.ticketmaster_detail_price_max_retries, 1))
        if response is None or response.status_code != 200:
            preview = (response.text or "")[:DETAIL_PREVIEW_LENGTH] if response is not None else ""
            self._logger.warning("Ticketmaster: detail fetch failed event_id=%s status=%s body=%s", event_id, getattr(response, "status_code", "none"), preview)
            return None
        return self._parse_json(response, "detail", event_id)

    def _wait_for_rate_limit(self) -> None:
        """Enforces a minimum interval between requests to stay under the OAuth rate limit."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < RATE_LIMIT_MIN_INTERVAL_SECONDS:
                time.sleep(RATE_LIMIT_MIN_INTERVAL_SECONDS - elapsed)
            self._last_request_time = time.monotonic()

    def _request_with_retry(self, url: str, params: Dict[str, Any], timeout: int, max_retries: int) -> Optional[requests.Response]:
        """Shared retry logic for both page and detail requests."""
        last_error = ""
        for attempt in range(1, max(max_retries, 1) + 1):
            try:
                self._wait_for_rate_limit()
                session = self._get_session()
                response = session.get(url, params=params, timeout=timeout)
                if response.status_code in AUTH_FAILURE_STATUS_CODES:
                    self._logger.error("Ticketmaster: auth failed status=%s url=%s", response.status_code, url)
                    return response
                if response.status_code in RETRYABLE_STATUS_CODES:
                    self._logger.warning("Ticketmaster: rate limited url=%s attempt=%s/%s", url, attempt, max_retries)
                    time.sleep(min(2 ** attempt, MAX_RETRY_BACKOFF_SECONDS))
                    continue
                return response
            except requests.exceptions.Timeout:
                last_error = f"Timeout url={url}"
            except Exception as exc:
                last_error = self._safe_error(exc)
            self._logger.warning("Ticketmaster: request failed url=%s attempt=%s/%s error=%s", url, attempt, max_retries, last_error)
            if attempt < max_retries:
                time.sleep(min(2 ** attempt, MAX_RETRY_BACKOFF_SECONDS))
        self._logger.error("Ticketmaster: retries exhausted url=%s error=%s", url, last_error)
        return None

    def _parse_json(self, response: requests.Response, stage: str, context: Any) -> Optional[Dict[str, Any]]:
        try:
            payload = response.json()
            return payload if isinstance(payload, dict) else None
        except Exception as exc:
            self._logger.warning("Ticketmaster: %s json parse failed context=%s reason=%s", stage, context, self._safe_error(exc))
            return None

    def _safe_error(self, exc: Exception) -> str:
        raw = f"{type(exc).__name__}: {exc}"
        key = settings.ticketmaster_api_key.strip()
        if key:
            raw = raw.replace(key, "***")
        return raw[:ERROR_PREVIEW_LENGTH]
