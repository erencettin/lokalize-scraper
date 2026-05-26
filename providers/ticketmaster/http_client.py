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

    def fetch_all_pages(self) -> List[Dict[str, Any]]:
        """Fetch all events via paginated Discovery API."""
        seen_ids: Set[str] = set()
        events: List[Dict[str, Any]] = []
        page = 0
        total_pages: Optional[int] = None

        while True:
            payload = self.fetch_page(page)
            if payload is None:
                self._logger.warning("Ticketmaster: page %s returned None, stopping", page)
                break

            raw_events, tp = self._parser_extract_page(payload)
            if total_pages is None and tp is not None:
                total_pages = tp
                self._logger.info("Ticketmaster: total_pages=%s", total_pages)

            if not raw_events:
                self._logger.info("Ticketmaster: empty page %s, stopping", page)
                break

            for item in raw_events:
                if not isinstance(item, dict):
                    continue
                event_id = str(item.get("eventId") or item.get("id") or "")
                if event_id and event_id not in seen_ids:
                    seen_ids.add(event_id)
                    events.append(item)

            page += 1
            self.last_fetched_pages = page

            if total_pages is not None and page >= total_pages:
                break

            max_pages = settings.ticketmaster_max_pages
            if max_pages > 0 and page >= max_pages:
                self._logger.info("Ticketmaster: max_pages=%s reached, stopping", max_pages)
                break

            time.sleep(settings.ticketmaster_page_delay_seconds)

        self._logger.info("Ticketmaster: fetched pages=%s unique_events=%s", page, len(events))
        return events

    def _parser_extract_page(self, payload: Dict[str, Any]):
        """Extract event list and total page count from a Discovery API response."""
        embedded = payload.get("_embedded") or {}
        raw_events = embedded.get("events") if isinstance(embedded, dict) else []
        page_info = payload.get("page") or {}
        total_pages = page_info.get("totalPages") if isinstance(page_info, dict) else None
        if not isinstance(raw_events, list):
            raw_events = []
        return raw_events, total_pages

    def fetch_page(self, page: int) -> Optional[Dict[str, Any]]:
        """Fetch one page from the Discovery API."""
        params = {
            "apikey": settings.ticketmaster_api_key,
            "countryCode": settings.ticketmaster_country_code,
            "size": max(settings.ticketmaster_size, 1),
            "page": page,
            "sort": DEFAULT_SORT,
        }
        response = self._request_with_retry(
            f"{BASE_URL}{EVENTS_ENDPOINT}",
            params,
            max(settings.ticketmaster_timeout_seconds, 1),
            max(settings.ticketmaster_max_retries, 1),
        )
        if response is None or response.status_code != 200:
            self._logger.warning(
                "Ticketmaster: page %s failed status=%s",
                page,
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
