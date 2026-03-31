"""HTTP client for Ticketmaster API fetch and retry behavior."""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Set

import requests

from config import settings
from providers.ticketmaster.constants import AUTH_FAILURE_STATUS_CODES, BASE_URL, DEFAULT_USER_AGENT, DETAIL_ENDPOINT_TEMPLATE, DETAIL_PREVIEW_LENGTH, ERROR_PREVIEW_LENGTH, EVENTS_ENDPOINT, RETRYABLE_STATUS_CODES

class TicketmasterHttpClient:
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
        """Fetch paginated event list and deduplicate by event id."""
        events: List[Dict[str, Any]] = []
        seen_ids: Set[str] = set()
        for page in range(max(settings.ticketmaster_max_pages, 1)):
            payload = self.fetch_page(page)
            if payload is None:
                self._logger.warning("Ticketmaster: page fetch failed page=%s, stopping", page); break
            self.last_fetched_pages += 1
            page_events = payload.get("events", [])
            total_pages = payload.get("total_pages")
            if not page_events:
                self._logger.info("Ticketmaster: page=%s has no events, stopping", page); break
            new_count = 0
            for item in page_events:
                event_id = str(item.get("id") or "") if isinstance(item, dict) else ""
                if event_id and event_id not in seen_ids:
                    seen_ids.add(event_id); events.append(item); new_count += 1
            self._logger.info("Ticketmaster: page=%s fetched=%s new=%s total_unique=%s", page, len(page_events), new_count, len(events))
            if new_count == 0 or (isinstance(total_pages, int) and page + 1 >= total_pages):
                break
            delay = max(settings.ticketmaster_page_delay_seconds, 0.0)
            if delay > 0: time.sleep(delay)
        return events

    def fetch_page(self, page: int) -> Optional[Dict[str, Any]]:
        """Fetch and parse one events page payload."""
        params = {"apikey": settings.ticketmaster_api_key, "countryCode": settings.ticketmaster_country_code, "city": settings.ticketmaster_city, "size": max(settings.ticketmaster_size, 1), "page": max(page, 0), "sort": "date,asc", "include": "priceRanges"}
        response = self._request_with_retry(f"{BASE_URL}{EVENTS_ENDPOINT}", params, max(settings.ticketmaster_timeout_seconds, 1), max(settings.ticketmaster_max_retries, 1))
        if response is None or response.status_code != 200:
            preview = (response.text or "")[:ERROR_PREVIEW_LENGTH] if response is not None else ""
            self._logger.warning("Ticketmaster: page fetch failed page=%s status=%s body=%s", page, getattr(response, "status_code", "none"), preview)
            return None
        payload = self._parse_json(response, "page", page)
        if payload is None: return None
        embedded = payload.get("_embedded") if isinstance(payload, dict) else {}
        page_info = payload.get("page") if isinstance(payload, dict) else {}
        events = embedded.get("events") if isinstance(embedded, dict) else []
        total_pages = page_info.get("totalPages") if isinstance(page_info, dict) else None
        return {"events": events if isinstance(events, list) else [], "total_pages": total_pages if isinstance(total_pages, int) else None}

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
        """Enforces a strict global 2 req/s limit across all parallel threads."""
        delay = 0.55
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < delay:
                time.sleep(delay - elapsed)
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
                    time.sleep(float(attempt))
                    continue
                return response
            except requests.exceptions.Timeout:
                last_error = f"Timeout url={url}"
            except Exception as exc:
                last_error = self._safe_error(exc)
            self._logger.warning("Ticketmaster: request failed url=%s attempt=%s/%s error=%s", url, attempt, max_retries, last_error)
            if attempt < max_retries:
                time.sleep(float(attempt))
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
