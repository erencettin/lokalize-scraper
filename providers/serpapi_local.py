from __future__ import annotations

import hashlib
import logging
import math
from datetime import datetime, timezone
from typing import List, Optional

from clients.serpapi_client import SerpApiClient
from config import build_serpapi_local_queries, settings
from models.normalized_place import NormalizedPlace
from utils.text_normalizer import clean_text


class SerpApiLocalProvider:
    _INT32_MAX = 2_147_483_647

    def __init__(self, serpapi_client: Optional[SerpApiClient] = None) -> None:
        self._logger = logging.getLogger(__name__)
        self._client = serpapi_client or SerpApiClient()

    @property
    def request_count(self) -> int:
        return self._client.request_count

    def fetch_places(self, city: Optional[str] = None) -> List[NormalizedPlace]:
        if not self._client.is_enabled:
            self._logger.warning("SerpApiLocalProvider: SERPAPI_API_KEY missing, provider is skipped.")
            return []

        resolved_city = (city or settings.serpapi_city).strip()
        now = datetime.now(timezone.utc)
        places: List[NormalizedPlace] = []
        dedup_keys: set[str] = set()

        for query in build_serpapi_local_queries(resolved_city):
            payload = self._client.search(engine="google_local", query=query["q"])
            payload_error = payload.get("error")
            if isinstance(payload_error, str) and payload_error.strip():
                self._logger.warning(
                    "SerpApiLocalProvider: query failed city=%s query=%s error=%s",
                    resolved_city,
                    query["q"],
                    payload_error,
                )
                continue
            local_results = payload.get("local_results")
            if not isinstance(local_results, list):
                continue

            for raw in local_results:
                if not isinstance(raw, dict):
                    continue
                place = self._map_place(
                    raw=raw,
                    category=query["category"],
                    city=resolved_city,
                    fetched_at=now,
                )
                if place is None:
                    continue
                dedup_key = f"{place.external_id}|{place.category}|{place.city}".lower()
                if dedup_key in dedup_keys:
                    continue
                dedup_keys.add(dedup_key)
                places.append(place)

        self._logger.info(
            "SerpApiLocalProvider: fetched=%s city=%s requests=%s",
            len(places),
            resolved_city,
            self.request_count,
        )
        return places

    def _map_place(
        self,
        *,
        raw: dict,
        category: str,
        city: str,
        fetched_at: datetime,
    ) -> Optional[NormalizedPlace]:
        title = clean_text(str(raw.get("title") or ""))
        if not title:
            return None

        address = self._clean_optional(raw.get("address"))
        gps = raw.get("gps_coordinates") if isinstance(raw.get("gps_coordinates"), dict) else {}
        latitude = self._to_float(gps.get("latitude"))
        longitude = self._to_float(gps.get("longitude"))
        rating = self._to_float(raw.get("rating"))
        reviews_count = self._to_int(raw.get("reviews"))
        external_id = self._clean_optional(raw.get("place_id")) or self._clean_optional(raw.get("data_id"))
        source_url = self._clean_optional(raw.get("place_id_search")) or self._clean_optional(raw.get("link"))
        if not external_id:
            external_id = self._build_fallback_id(title=title, address=address, category=category, city=city)

        return NormalizedPlace(
            source="serpapi_google_local",
            external_id=external_id,
            title=title,
            category=category,
            address=address,
            latitude=latitude,
            longitude=longitude,
            rating=rating,
            reviews_count=reviews_count,
            phone=self._clean_optional(raw.get("phone")),
            hours=self._serialize_hours(raw.get("hours")),
            thumbnail_url=self._clean_optional(raw.get("thumbnail")),
            source_url=source_url,
            city=city,
            fetched_at=fetched_at,
        )

    def _build_fallback_id(self, *, title: str, address: Optional[str], category: str, city: str) -> str:
        text = f"{title}|{address or ''}|{category}|{city}".lower()
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
        return f"serpapi-local-{digest[:20]}"

    @staticmethod
    def _serialize_hours(value: object) -> Optional[str]:
        if isinstance(value, str):
            normalized = clean_text(value)
            return normalized or None
        if isinstance(value, dict):
            open_text = value.get("open_now")
            if isinstance(open_text, str):
                normalized = clean_text(open_text)
                return normalized or None
        return None

    @staticmethod
    def _clean_optional(value: object) -> Optional[str]:
        if value is None:
            return None
        text = clean_text(str(value))
        return text or None

    @staticmethod
    def _to_float(value: object) -> Optional[float]:
        try:
            if value is None:
                return None
            parsed = float(value)
            if not math.isfinite(parsed):
                return None
            return parsed
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(value: object) -> Optional[int]:
        try:
            if value is None:
                return None
            parsed = int(value)
            if parsed < 0 or parsed > SerpApiLocalProvider._INT32_MAX:
                return None
            return parsed
        except (TypeError, ValueError):
            return None
