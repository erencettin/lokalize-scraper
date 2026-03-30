from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from models.normalized_event import NormalizedEvent, NormalizedOccurrence
from utils.text_normalizer import TextNormalizer


def build_occurrence_dedup_key(title: str, local_date: str, local_time: str) -> str:
    """Build a stable key used by providers for local occurrence de-duplication."""
    normalized_title = TextNormalizer.normalize_for_match(title)
    return f"{normalized_title}|{local_date}|{local_time}"


@dataclass(frozen=True)
class EventRecordMatchKeys:
    id_keys: Tuple[str, ...]
    url_keys: Tuple[str, ...]
    title_date_city_key: Optional[str]
    venue_key: Optional[str]


def _as_clean_string(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_text_key(value: object) -> str:
    return TextNormalizer.normalize_for_match(_as_clean_string(value))


def _normalize_date_key(value: object) -> str:
    raw = _as_clean_string(value)
    if not raw:
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return raw
    if re.match(r"^\d{4}-\d{2}-\d{2}[tT]", raw):
        return raw[:10]
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.date().isoformat()
    except ValueError:
        return _normalize_text_key(raw)


def _normalize_url_key(value: object) -> str:
    raw = _as_clean_string(value)
    if not raw:
        return ""
    parsed = urlparse(raw)
    if not parsed.scheme and not parsed.netloc and "." in raw and "/" not in raw:
        parsed = urlparse(f"https://{raw}")

    host = (parsed.netloc or "").lower()
    if "@" in host:
        host = host.split("@", 1)[-1]
    if ":" in host:
        host = host.split(":", 1)[0]
    host = host.removeprefix("www.")

    path = parsed.path or ""
    if path != "/":
        path = path.rstrip("/")

    if not host and not path:
        return ""
    return f"{host}{path}".strip()


def _extract_first_occurrence(record: dict) -> Optional[dict]:
    occurrences = record.get("occurrences")
    if not isinstance(occurrences, list):
        return None
    for occurrence in occurrences:
        if isinstance(occurrence, dict):
            return occurrence
    return None


def _extract_record_date(record: dict) -> str:
    occurrence = _extract_first_occurrence(record)
    if occurrence:
        for key in ("local_date", "date", "start_at_utc", "start_at", "datetime"):
            normalized = _normalize_date_key(occurrence.get(key))
            if normalized:
                return normalized
    for key in ("date", "local_date", "start_at_utc", "start_at", "datetime"):
        normalized = _normalize_date_key(record.get(key))
        if normalized:
            return normalized
    return ""


def _extract_record_venue_key(record: dict) -> str:
    occurrence = _extract_first_occurrence(record)
    if occurrence:
        for key in ("venue_name", "venue", "place_name", "location"):
            normalized = _normalize_text_key(occurrence.get(key))
            if normalized:
                return normalized
    for key in ("venue_name", "venue", "place_name", "location"):
        normalized = _normalize_text_key(record.get(key))
        if normalized:
            return normalized
    return ""


def _extract_record_ids(record: dict) -> Tuple[str, ...]:
    keys: List[str] = []
    seen: set[str] = set()

    def add(value: object) -> None:
        normalized = _normalize_text_key(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            keys.append(normalized)

    for field in ("id", "external_id", "event_id"):
        add(record.get(field))

    occurrence = _extract_first_occurrence(record)
    if occurrence and isinstance(occurrence.get("sources"), list):
        for source in occurrence["sources"]:
            if not isinstance(source, dict):
                continue
            add(source.get("external_id"))
            add(source.get("id"))

    return tuple(keys)


def _extract_record_urls(record: dict) -> Tuple[str, ...]:
    keys: List[str] = []
    seen: set[str] = set()

    def add(value: object) -> None:
        normalized = _normalize_url_key(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            keys.append(normalized)

    for field in ("source_url", "url", "link"):
        add(record.get(field))

    occurrence = _extract_first_occurrence(record)
    if occurrence and isinstance(occurrence.get("sources"), list):
        for source in occurrence["sources"]:
            if not isinstance(source, dict):
                continue
            add(source.get("source_url"))
            add(source.get("deep_link_url"))
            add(source.get("url"))

    return tuple(keys)


class MatchingService:
    def __init__(self, existing_items: List[dict]):
        self.existing_items = existing_items
        self._text_normalizer = TextNormalizer()

    def find_match(self, occurrence: NormalizedOccurrence, event_title: str, city_name: str) -> Tuple[Optional[dict], str]:
        """
        Implements 4-step matching logic:
        1. Exact match by fingerprint (Title + Venue + Date + Time)
        2. Probable match by similar title and venue window
        3. Fallback to new logical event
        """
        current_fingerprint = self._text_normalizer.generate_fingerprint(
            event_title, occurrence.venue_name, occurrence.local_date, occurrence.local_time
        )

        for item in self.existing_items:
            if item.get("fingerprint") == current_fingerprint:
                return item, "strong"

        current_logical_key = self._text_normalizer.generate_logical_key(event_title, city_name)
        for item in self.existing_items:
            if item.get("logical_event_key") == current_logical_key:
                return item, "probable"

        return None, "weak"

    @staticmethod
    def build_occurrence_dedup_key(event: NormalizedEvent) -> str:
        """Build a stable key used by providers for local occurrence de-duplication."""
        if not event.occurrences:
            return TextNormalizer.normalize_for_match(event.title)
        occurrence = event.occurrences[0]
        return build_occurrence_dedup_key(event.title, occurrence.local_date, occurrence.local_time)

    @staticmethod
    def build_event_match_keys(record: dict) -> EventRecordMatchKeys:
        title = _normalize_text_key(record.get("title") or record.get("name"))
        date_key = _extract_record_date(record)
        city_key = _normalize_text_key(record.get("city_name") or record.get("city"))
        title_date_city_key = f"{title}|{date_key}|{city_key}" if title and date_key and city_key else None
        venue_key = _extract_record_venue_key(record) or None

        return EventRecordMatchKeys(
            id_keys=_extract_record_ids(record),
            url_keys=_extract_record_urls(record),
            title_date_city_key=title_date_city_key,
            venue_key=venue_key,
        )

    @staticmethod
    def find_event_match_index(
        *,
        record: dict,
        merged_records: Sequence[dict],
        id_index: Dict[str, int],
        url_index: Dict[str, int],
        title_date_city_index: Dict[str, List[int]],
    ) -> Optional[int]:
        keys = MatchingService.build_event_match_keys(record)

        for key in keys.id_keys:
            if key in id_index:
                return id_index[key]

        for key in keys.url_keys:
            if key in url_index:
                return url_index[key]

        if not keys.title_date_city_key:
            return None
        candidates = title_date_city_index.get(keys.title_date_city_key, [])
        if not candidates:
            return None

        if not keys.venue_key:
            return candidates[0]
        for candidate_idx in candidates:
            candidate = merged_records[candidate_idx]
            candidate_keys = MatchingService.build_event_match_keys(candidate)
            if candidate_keys.venue_key == keys.venue_key:
                return candidate_idx
        return candidates[0]
