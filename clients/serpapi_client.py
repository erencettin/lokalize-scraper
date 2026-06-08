from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import requests

from config import settings


class SerpApiClient:
    _BASE_URL = "https://serpapi.com/search.json"

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self._api_key = settings.serpapi_api_key.strip()
        self._timeout_seconds = max(settings.serpapi_timeout_seconds, 1)
        self._max_attempts = max(settings.serpapi_max_attempts, 1)
        self._session = requests.Session()
        self.request_count = 0

    @property
    def is_enabled(self) -> bool:
        return bool(self._api_key)

    def search(
        self,
        *,
        engine: str,
        query: Optional[str] = None,
        location: Optional[str] = None,
        hl: str = "tr",
        gl: str = "tr",
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.is_enabled:
            raise RuntimeError("SERPAPI_API_KEY is missing.")

        params: Dict[str, Any] = {
            "api_key": self._api_key,
            "engine": engine,
            "hl": hl,
            "gl": gl,
        }
        if query and query.strip():
            params["q"] = query.strip()
        if location and location.strip():
            params["location"] = location.strip()
        if extra_params:
            params.update(extra_params)

        last_error: Optional[str] = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                self.request_count += 1
                response = self._session.get(
                    self._BASE_URL,
                    params=params,
                    timeout=self._timeout_seconds,
                )
                status_code = response.status_code
                if 400 <= status_code < 500:
                    raise RuntimeError(
                        f"SerpAPI request failed (status={status_code}): non-retryable client error."
                    )
                if 500 <= status_code < 600:
                    last_error = f"server error status={status_code}"
                    self._logger.warning(
                        "SerpAPI transient failure engine=%s attempt=%s/%s status=%s",
                        engine,
                        attempt,
                        self._max_attempts,
                        status_code,
                    )
                    if attempt < self._max_attempts:
                        time.sleep(float(attempt))
                        continue
                    break
                payload = response.json()
                if not isinstance(payload, dict):
                    raise RuntimeError("SerpAPI response payload is not a JSON object.")
                return payload
            except requests.Timeout:
                last_error = "timeout"
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}"
            except ValueError:
                last_error = "invalid json"
            except RuntimeError:
                raise

            self._logger.warning(
                "SerpAPI request failed engine=%s attempt=%s/%s reason=%s",
                engine,
                attempt,
                self._max_attempts,
                last_error,
            )
            if attempt < self._max_attempts:
                time.sleep(float(attempt))

        raise RuntimeError(
            f"SerpAPI request exhausted retries engine={engine} reason={last_error or 'unknown'}"
        )
