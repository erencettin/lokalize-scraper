"""HTTP client for Bilet.com Affiliate API with token caching and retry logic."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import threading

import jwt
import requests

from config import settings
from providers.biletcom.constants import (
    BASE_URL,
    DEFAULT_DETAIL_WORKERS,
    DETAIL_REQUEST_DELAY_SECONDS,
    ERROR_PREVIEW_LENGTH,
    LIST_ENDPOINT,
    MAX_RETRIES,
    MAX_RETRY_BACKOFF_SECONDS,
    RETRY_BACKOFF_BASE,
    RETRYABLE_STATUS_CODES,
    TOKEN_ENDPOINT,
    TOKEN_EXPIRY_BUFFER_SECONDS,
)


class BiletcomHttpClient:
    """Manages authentication and HTTP calls for the Bilet.com sale API."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self._session: Optional[requests.Session] = None
        self._token: Optional[str] = None
        self._token_exp: float = 0.0
        self._token_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def setup_session(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "Accept-Language": "tr-TR,tr;q=0.9",
            "User-Agent": "LokalizeApp/1.0",
        })

    def close_session(self) -> None:
        if self._session:
            try:
                self._session.close()
            except Exception as exc:
                self._logger.warning("bilet.com: session close failed: %s", self._safe_error(exc))
            finally:
                self._session = None

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def get_token(self) -> Optional[str]:
        """Return a valid cached JWT, refreshing it when expired.

        Thread-safe: the lock ensures only one thread fetches a new token
        even when multiple workers discover expiry simultaneously.
        """
        # Fast path: check without lock first (common case — token is valid).
        if self._token and time.time() < self._token_exp - TOKEN_EXPIRY_BUFFER_SECONDS:
            return self._token

        with self._token_lock:
            # Re-check inside the lock; another thread may have refreshed already.
            if self._token and time.time() < self._token_exp - TOKEN_EXPIRY_BUFFER_SECONDS:
                return self._token

            return self._refresh_token()

    def _refresh_token(self) -> Optional[str]:
        """Fetch a fresh token from the API. Must be called while holding _token_lock."""
        self._logger.info("bilet.com: fetching new token")
        url = f"{BASE_URL}{TOKEN_ENDPOINT}"
        try:
            resp = self._session.get(
                url,
                headers={
                    "x-client-id": settings.biletcom_client_id,
                    "x-client-secret": settings.biletcom_client_secret,
                },
                timeout=settings.biletcom_timeout_seconds,
            )
        except Exception as exc:
            self._logger.error("bilet.com: token fetch connection failed: %s", self._safe_error(exc))
            return None

        if resp.status_code != 200:
            self._logger.error("bilet.com: token fetch HTTP %s — %s", resp.status_code, resp.text[:200])
            return None

        try:
            data = resp.json()
        except Exception:
            self._logger.error("bilet.com: token response JSON parse failed — %s", resp.text[:200])
            return None

        # Response shape: {"status":"success","data":{"token":"<jwt>"}}
        token: Optional[str] = None
        if isinstance(data, str):
            token = data
        elif isinstance(data, dict):
            token = data.get("token") or data.get("access_token")
            if not token:
                nested = data.get("data")
                if isinstance(nested, str):
                    token = nested
                elif isinstance(nested, dict):
                    token = nested.get("token") or nested.get("access_token")

        if not token or not isinstance(token, str):
            self._logger.error("bilet.com: unexpected token response shape: %s", str(data)[:200])
            return None

        # Decode exp claim without signature verification (we trust the server).
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            self._token_exp = float(payload.get("exp", time.time() + 7200))
        except Exception:
            self._token_exp = time.time() + 7200

        self._token = token
        self._logger.info("bilet.com: token obtained, expires in ~%.0fs", self._token_exp - time.time())
        return self._token

    def _auth_header(self) -> Dict[str, str]:
        token = self.get_token()
        return {"Authorization": f"Bearer {token}"} if token else {}

    # ------------------------------------------------------------------
    # API calls
    # ------------------------------------------------------------------

    def fetch_listing(self) -> Optional[List[Dict[str, Any]]]:
        """GET /list — returns the lightweight listing of all activities."""
        url = f"{BASE_URL}{LIST_ENDPOINT}"
        resp = self._request_with_retry(url, {})
        if resp is None:
            return None
        data = self._parse_json(resp, "listing")
        if data is None:
            return None
        items = data.get("data")
        if not isinstance(items, list):
            self._logger.error("bilet.com: /list unexpected shape — %s", str(data)[:200])
            return None
        self._logger.info("bilet.com: /list returned %d items", len(items))
        return items

    def fetch_activity_detail(self, activity_id: int) -> Optional[Dict[str, Any]]:
        """GET /list/{id} — returns detailed activity with options."""
        url = f"{BASE_URL}{LIST_ENDPOINT}/{activity_id}"
        resp = self._request_with_retry(url, {})
        if resp is None:
            return None
        data = self._parse_json(resp, f"detail/{activity_id}")
        if data is None:
            return None
        detail = data.get("data")
        if not isinstance(detail, dict):
            self._logger.warning("bilet.com: detail/%d unexpected shape", activity_id)
            return None
        return detail

    # ------------------------------------------------------------------
    # Internal request helpers
    # ------------------------------------------------------------------

    def _request_with_retry(
        self,
        url: str,
        params: Dict[str, Any],
    ) -> Optional[requests.Response]:
        last_error = ""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                headers = self._auth_header()
                resp = self._session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=settings.biletcom_timeout_seconds,
                )
                if resp.status_code == 401:
                    # Token expired — clear cache and retry once with a fresh token.
                    self._logger.warning("bilet.com: 401 on %s — clearing token", url)
                    self._token = None
                    self._token_exp = 0.0
                    new_headers = self._auth_header()
                    if not new_headers:
                        return resp
                    resp = self._session.get(
                        url,
                        params=params,
                        headers=new_headers,
                        timeout=settings.biletcom_timeout_seconds,
                    )
                if resp.status_code in RETRYABLE_STATUS_CODES:
                    backoff = min(RETRY_BACKOFF_BASE ** attempt, MAX_RETRY_BACKOFF_SECONDS)
                    self._logger.warning(
                        "bilet.com: HTTP %s on %s attempt=%d/%d, backing off %.1fs",
                        resp.status_code, url, attempt, MAX_RETRIES, backoff,
                    )
                    time.sleep(backoff)
                    continue
                return resp
            except requests.exceptions.Timeout:
                last_error = f"Timeout url={url}"
            except Exception as exc:
                last_error = self._safe_error(exc)
            self._logger.warning(
                "bilet.com: request failed url=%s attempt=%d/%d error=%s",
                url, attempt, MAX_RETRIES, last_error,
            )
            if attempt < MAX_RETRIES:
                time.sleep(min(RETRY_BACKOFF_BASE ** attempt, MAX_RETRY_BACKOFF_SECONDS))
        self._logger.error("bilet.com: retries exhausted url=%s error=%s", url, last_error)
        return None

    def _parse_json(self, resp: requests.Response, stage: str) -> Optional[Dict[str, Any]]:
        try:
            data = resp.json()
            return data if isinstance(data, dict) else None
        except Exception as exc:
            self._logger.warning(
                "bilet.com: %s json parse failed status=%s reason=%s",
                stage, resp.status_code, self._safe_error(exc),
            )
            return None

    def _safe_error(self, exc: Exception) -> str:
        raw = f"{type(exc).__name__}: {exc}"
        secret = settings.biletcom_client_secret.strip()
        if secret:
            raw = raw.replace(secret, "***")
        client_id = settings.biletcom_client_id.strip()
        if client_id:
            raw = raw.replace(client_id, "***")
        return raw[:ERROR_PREVIEW_LENGTH]
