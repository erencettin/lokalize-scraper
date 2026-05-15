"""HTTP client for Ticketmaster API fetch and retry behavior."""
from __future__ import annotations

import gzip
import io
import json
import logging
import threading
import time
import zipfile
from typing import Any, Dict, List, Optional, Set

import requests

from config import settings
from providers.base_http_client import BaseHttpClient
from providers.ticketmaster.constants import AUTH_FAILURE_STATUS_CODES, BASE_URL, FEED_BASE_URL, DEFAULT_USER_AGENT, DETAIL_ENDPOINT_TEMPLATE, DETAIL_PREVIEW_LENGTH, ERROR_PREVIEW_LENGTH, EVENTS_ENDPOINT, RETRYABLE_STATUS_CODES

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
        """Download Discovery Feed ZIP and return deduplicated event list."""
        raw_events = self._fetch_feed_as_events()
        if raw_events is None:
            self._logger.error("Ticketmaster: feed download failed, no events returned")
            return []
        seen_ids: Set[str] = set()
        events: List[Dict[str, Any]] = []
        for item in raw_events:
            if not isinstance(item, dict):
                continue
            event_id = str(item.get("id") or "")
            if event_id and event_id not in seen_ids:
                seen_ids.add(event_id)
                events.append(item)
        self.last_fetched_pages = 1
        self._logger.info("Ticketmaster: feed total unique events=%s", len(events))
        return events

    def _fetch_feed_as_events(self) -> Optional[List[Dict[str, Any]]]:
        """Download Discovery Feed ZIP/GZIP and extract event list."""
        params = {
            "apikey": settings.ticketmaster_api_key,
            "countryCode": settings.ticketmaster_country_code,
        }
        response = self._request_with_retry(
            f"{FEED_BASE_URL}{EVENTS_ENDPOINT}",
            params,
            max(settings.ticketmaster_timeout_seconds, 1),
            max(settings.ticketmaster_max_retries, 1),
        )
        if response is None or response.status_code != 200:
            self._logger.warning(
                "Ticketmaster: feed request failed status=%s",
                getattr(response, "status_code", "none"),
            )
            return None
        content = response.content
        if not content:
            self._logger.warning("Ticketmaster: feed response body is empty")
            return None
        # Try ZIP (magic bytes PK)
        if content[:2] == b"PK":
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    json_names = [n for n in zf.namelist() if n.lower().endswith(".json")]
                    if not json_names:
                        self._logger.warning("Ticketmaster: ZIP contains no JSON file, names=%s", zf.namelist())
                        return None
                    json_bytes = zf.read(json_names[0])
                    self._logger.info("Ticketmaster: extracted %s from ZIP (%d bytes)", json_names[0], len(json_bytes))
                    return self._parse_feed_json(json_bytes)
            except zipfile.BadZipFile as exc:
                self._logger.warning("Ticketmaster: ZIP parse failed reason=%s", exc)
        # Try GZIP (magic bytes 1f 8b)
        if content[:2] == b"\x1f\x8b":
            try:
                return self._parse_feed_json(gzip.decompress(content))
            except Exception as exc:
                self._logger.warning("Ticketmaster: GZIP decompress failed reason=%s", exc)
        # Try plain JSON
        return self._parse_feed_json(content)

    def _parse_feed_json(self, data: bytes) -> Optional[List[Dict[str, Any]]]:
        """Parse raw bytes as JSON and extract event list."""
        try:
            raw = json.loads(data)
        except Exception as exc:
            self._logger.warning("Ticketmaster: feed JSON parse failed reason=%s", exc)
            return None
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            embedded = raw.get("_embedded") or {}
            if isinstance(embedded, dict) and isinstance(embedded.get("events"), list):
                return embedded["events"]
            if isinstance(raw.get("events"), list):
                return raw["events"]
        self._logger.warning("Ticketmaster: feed JSON structure unrecognised type=%s", type(raw).__name__)
        return None

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
                    time.sleep(min(2 ** attempt, 60))
                    continue
                return response
            except requests.exceptions.Timeout:
                last_error = f"Timeout url={url}"
            except Exception as exc:
                last_error = self._safe_error(exc)
            self._logger.warning("Ticketmaster: request failed url=%s attempt=%s/%s error=%s", url, attempt, max_retries, last_error)
            if attempt < max_retries:
                time.sleep(min(2 ** attempt, 60))
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
