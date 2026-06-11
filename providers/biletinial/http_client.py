"""HTTP client for fetching the Biletinial affiliate feed with retry/backoff."""
from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from config import settings
from providers.biletinial.constants import (
    ERROR_PREVIEW_LENGTH,
    MAX_RETRY_BACKOFF_SECONDS,
    RETRY_BACKOFF_BASE,
    RETRYABLE_STATUS_CODES,
    USER_AGENT,
)


class BiletinialHttpClient:
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def fetch_feed(self, url: str) -> Optional[bytes]:
        """GET the feed and return raw bytes, or None on failure."""
        last_error = ""
        max_retries = max(1, settings.biletinial_max_retries)

        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.get(
                    url,
                    timeout=settings.biletinial_timeout_seconds,
                    headers={"User-Agent": USER_AGENT, "Accept": "application/xml"},
                )
            except requests.exceptions.Timeout:
                last_error = f"Timeout url={url}"
            except Exception as exc:
                last_error = self._safe_error(exc)
            else:
                if resp.status_code == 200:
                    return resp.content
                if resp.status_code in RETRYABLE_STATUS_CODES:
                    last_error = f"HTTP {resp.status_code}"
                else:
                    self._logger.error(
                        "Biletinial: HTTP %s for %s — body: %s",
                        resp.status_code, url, resp.text[:ERROR_PREVIEW_LENGTH],
                    )
                    return None

            if attempt < max_retries:
                backoff = min(RETRY_BACKOFF_BASE ** attempt, MAX_RETRY_BACKOFF_SECONDS)
                self._logger.warning(
                    "Biletinial: request failed url=%s attempt=%d/%d error=%s, retrying in %.0fs",
                    url, attempt, max_retries, last_error, backoff,
                )
                time.sleep(backoff)

        self._logger.error("Biletinial: retries exhausted url=%s error=%s", url, last_error)
        return None

    def _safe_error(self, exc: Exception) -> str:
        return f"{type(exc).__name__}: {exc}"[:ERROR_PREVIEW_LENGTH]
