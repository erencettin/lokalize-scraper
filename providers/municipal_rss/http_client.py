"""HTTP client for municipal RSS provider."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import requests

from config import settings
from providers.base_http_client import BaseHttpClient
from providers.municipal_rss.constants import DEFAULT_ACCEPT_HEADER, DEFAULT_USER_AGENT, RETRYABLE_STATUS_CODES


class RssHttpClient(BaseHttpClient):
    """Wrap session lifecycle and retrying HTTP fetch operations."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self._session: Optional[requests.Session] = None

    @property
    def session(self) -> Optional[requests.Session]:
        """Expose underlying session for tests and compatibility usage."""
        return self._session

    @session.setter
    def session(self, value: Any) -> None:
        self._session = value

    def setup_session(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({"Accept": DEFAULT_ACCEPT_HEADER, "User-Agent": DEFAULT_USER_AGENT})

    def close_session(self) -> None:
        try:
            if self._session is not None:
                self._session.close()
        except Exception as exc:
            self._logger.warning("MunicipalRSS: session close failed reason=%s", exc)
        finally:
            self._session = None

    def fetch_xml(self, url: str) -> Optional[str]:
        response = self._request(url)
        return response.text if response is not None else None

    def fetch_text(self, url: str) -> str:
        response = self._request(url)
        return response.text if response is not None else ""

    def fetch_json(self, url: str) -> Optional[object]:
        response = self._request(url)
        if response is None:
            return None
        try:
            return response.json()
        except Exception as exc:
            self._logger.warning("MunicipalRSS: invalid JSON url=%s reason=%s", url, exc)
            return None

    def _request(self, url: str) -> Optional[requests.Response]:
        if self._session is None:
            self._logger.error("MunicipalRSS: fetch without active session url=%s", url)
            return None
        timeout = max(settings.municipal_rss_timeout_seconds, 1)
        retries = max(settings.municipal_rss_max_retries, 1)
        return self._request_with_retry(url, timeout, retries)

    def _request_with_retry(self, url: str, timeout: int, retries: int) -> Optional[requests.Response]:
        for attempt in range(1, retries + 1):
            response = self._single_attempt(url, timeout)
            if response is not None:
                return response
            if attempt < retries:
                time.sleep(float(attempt))
        return None

    def _single_attempt(self, url: str, timeout: int) -> Optional[requests.Response]:
        try:
            response = self._session.get(url, timeout=timeout)
            if response.status_code == 200:
                return response
            if response.status_code in RETRYABLE_STATUS_CODES:
                self._logger.warning("MunicipalRSS: retryable status url=%s status=%s", url, response.status_code)
                return None
            self._logger.info("MunicipalRSS: skip url=%s status=%s", url, response.status_code)
            return None
        except Exception as exc:
            self._logger.warning("MunicipalRSS: request failed url=%s reason=%s", url, exc)
            return None
