"""Date extraction helpers for WordPress event payloads."""
from __future__ import annotations
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
import pytz
from providers.municipal_rss.constants import ISTANBUL_TIMEZONE, TIME_SEARCH_WINDOW, TURKISH_MONTHS, WORDPRESS_DATE_KEYS, WORDPRESS_EVENT_KEYS, WORDPRESS_TEXT_DATE_PATTERNS, WORDPRESS_TIME_KEYS
from utils.text_normalizer import clean_text
class WordPressDateExtractor:
    """Extract datetime values from WordPress payloads and page text."""

    def __init__(self, date_parser: Callable[[str], Optional[datetime]]) -> None:
        self._parse_date = date_parser
        self._istanbul_tz = pytz.timezone(ISTANBUL_TIMEZONE)

    def parse_date(self, value: str) -> Optional[datetime]:
        return self._parse_date(value)

    def extract_event_date(self, entry: Dict[str, Any], text: str, post_date: Optional[datetime]) -> Optional[datetime]:
        for container in self._containers(entry):
            combined = self._extract_datetime_field(container, WORDPRESS_EVENT_KEYS)
            parsed = self._parse_date(combined) if combined else None
            if parsed is not None:
                return parsed
            date_value = self._extract_datetime_field(container, WORDPRESS_DATE_KEYS)
            time_value = self._extract_datetime_field(container, WORDPRESS_TIME_KEYS)
            parsed = self._parse_date(self._combine(date_value, time_value)) if date_value else None
            if parsed is not None:
                return parsed
        return self._extract_date_from_content(text, post_date)

    def _containers(self, entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        values = [entry, entry.get("acf"), entry.get("meta"), entry.get("event"), entry.get("event_listing")]
        return [value for value in values if isinstance(value, dict)]

    def _extract_datetime_field(self, container: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[str]:
        value = self._extract_first_value(container, keys)
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return self._timestamp_to_iso(float(value))
        if isinstance(value, dict):
            return self._extract_datetime_from_mapping(value)
        text = clean_text(str(value))
        return text if text else None

    def _extract_first_value(self, container: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[Any]:
        for key in keys:
            if key not in container:
                continue
            value = container.get(key)
            return value[0] if isinstance(value, list) and value else value
        return None

    def _extract_datetime_from_mapping(self, mapping: Dict[str, Any]) -> Optional[str]:
        rendered = mapping.get("rendered") or mapping.get("value")
        if rendered:
            return clean_text(str(rendered))
        date_value = self._extract_datetime_field(mapping, WORDPRESS_DATE_KEYS)
        time_value = self._extract_datetime_field(mapping, WORDPRESS_TIME_KEYS)
        if date_value:
            return self._combine(date_value, time_value)
        text = " ".join(str(item) for item in mapping.values() if isinstance(item, (str, int, float)))
        return self._extract_datetime_from_text(text)

    def _combine(self, date_value: str, time_value: Optional[str]) -> str:
        date_text = clean_text(date_value)
        time_text = clean_text(time_value or "")
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_text):
            return f"{date_text}T{time_text}:00+03:00" if time_text else f"{date_text}T00:00:00+03:00"
        return f"{date_text} {time_text}" if time_text and re.match(r"^\d{2}:\d{2}$", time_text) else date_text

    def _extract_datetime_from_text(self, text: str) -> Optional[str]:
        cleaned = clean_text(text)
        for pattern in WORDPRESS_TEXT_DATE_PATTERNS:
            match = re.search(pattern, cleaned)
            if match:
                return clean_text(match.group(1))
        return None

    def _extract_date_from_content(self, text: str, post_date: Optional[datetime]) -> Optional[datetime]:
        normalized = self._normalize_turkish(clean_text(text))
        if not normalized:
            return None
        candidates = self._range_candidates(normalized, post_date)
        candidates.extend(self._numeric_candidates(normalized, post_date))
        if not candidates:
            return None
        now_local = datetime.now(self._istanbul_tz)
        reference = post_date.astimezone(self._istanbul_tz) if post_date else now_local
        reference = now_local if reference < now_local else reference
        future = sorted([value for value in candidates if value.date() >= reference.date()])
        selected = future[0] if future else sorted(candidates)[0]
        return selected.astimezone(pytz.UTC)

    def _range_candidates(self, text: str, post_date: Optional[datetime]) -> List[datetime]:
        candidates: List[datetime] = []
        pattern = re.compile(r"(\d{1,2})\s*(?:[-–—/]\s*(\d{1,2})|\s+ve\s+(\d{1,2}))?\s+([a-z]+)(?:\s+(\d{4}))?")
        months = {self._normalize_turkish(key): value for key, value in TURKISH_MONTHS.items()}
        for match in pattern.finditer(text):
            month = months.get(match.group(4))
            if month is None:
                continue
            year = int(match.group(5)) if match.group(5) else None
            days = [int(match.group(1))] + ([int(match.group(2) or match.group(3))] if (match.group(2) or match.group(3)) else [])
            for day in days:
                candidate = self._build_local_datetime(day, month, year, self._extract_time_after(text, match.end()), post_date)
                if candidate is not None:
                    candidates.append(candidate)
        return candidates

    def _numeric_candidates(self, text: str, post_date: Optional[datetime]) -> List[datetime]:
        candidates: List[datetime] = []
        for pattern in (re.compile(r"(\d{2})\.(\d{2})\.(\d{4})"), re.compile(r"(\d{2})/(\d{2})/(\d{4})")):
            for match in pattern.finditer(text):
                day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                candidate = self._build_local_datetime(day, month, year, self._extract_time_after(text, match.end()), post_date)
                if candidate is not None:
                    candidates.append(candidate)
        return candidates

    def _build_local_datetime(self, day: int, month: int, year: Optional[int], time_value: Optional[Tuple[int, int]], post_date: Optional[datetime]) -> Optional[datetime]:
        reference = post_date.astimezone(self._istanbul_tz) if post_date else datetime.now(self._istanbul_tz)
        target_year = year or reference.year
        if year is None:
            try:
                if datetime(target_year, month, day).date() < reference.date():
                    target_year += 1
            except ValueError:
                return None
        hour, minute = time_value or (0, 0)
        try:
            return self._istanbul_tz.localize(datetime(target_year, month, day, hour, minute))
        except ValueError:
            return None

    def _extract_time_after(self, text: str, index: int) -> Optional[Tuple[int, int]]:
        window = text[index : index + TIME_SEARCH_WINDOW]
        match = re.search(r"(\d{1,2})[:\.](\d{2})", window)
        if not match:
            return None
        hour, minute = int(match.group(1)), int(match.group(2))
        return (hour, minute) if hour <= 23 and minute <= 59 else None

    def _normalize_turkish(self, value: str) -> str:
        return value.lower().replace("ı", "i").replace("ğ", "g").replace("ü", "u").replace("ş", "s").replace("ö", "o").replace("ç", "c")

    def _timestamp_to_iso(self, value: float) -> str:
        timestamp = value / 1000.0 if value > 100000000000 else value
        return datetime.utcfromtimestamp(timestamp).replace(tzinfo=pytz.UTC).isoformat()
