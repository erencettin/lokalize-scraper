import hashlib
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import pytz
import requests

from config import settings
from models.normalized_event import (
    NormalizedEvent,
    NormalizedOccurrence,
    NormalizedSource,
    PriceInfo,
)
from providers.base_provider import BaseProvider
from utils.date_parser import DateParser


class MunicipalRssProvider(BaseProvider):
    ISTANBUL_TZ = pytz.timezone("Europe/Istanbul")

    CATEGORY_MAP = {
        "konser": "concert",
        "muzik": "concert",
        "müzik": "concert",
        "tiyatro": "theatre",
        "stand up": "standup",
        "stand-up": "standup",
        "komedi": "standup",
        "festival": "festival",
        "sinema": "cinema",
        "film": "cinema",
        "sergi": "exhibition",
        "atolye": "experience",
        "atölye": "experience",
        "workshop": "experience",
        "etkinlik": "experience",
    }
    TURKISH_MONTHS = {
        "ocak": 1,
        "subat": 2,
        "şubat": 2,
        "mart": 3,
        "nisan": 4,
        "mayis": 5,
        "mayıs": 5,
        "haziran": 6,
        "temmuz": 7,
        "agustos": 8,
        "ağustos": 8,
        "eylul": 9,
        "eylül": 9,
        "ekim": 10,
        "kasim": 11,
        "kasım": 11,
        "aralik": 12,
        "aralık": 12,
    }

    def __init__(self) -> None:
        super().__init__("MunicipalRSS", mode="http")
        self.logger = logging.getLogger(__name__)
        self.session: Optional[requests.Session] = None

    def fetch_and_parse(self) -> List[NormalizedEvent]:
        if not settings.municipal_rss_enabled:
            self.logger.info("MunicipalRSS: disabled by config, skipping provider")
            return []

        rss_urls = self._resolve_rss_urls()
        if not rss_urls:
            self.logger.warning("MunicipalRSS: no RSS URLs configured, skipping")
            return []

        self._setup_session()
        try:
            events: List[NormalizedEvent] = []
            seen_keys: Set[str] = set()
            for url in rss_urls:
                items = self._fetch_source_items(url)
                self.logger.info("MunicipalRSS: feed=%s items=%s", url, len(items))
                for item in items:
                    normalized = self._normalize_item(item)
                    if normalized is None:
                        continue
                    key = f"{normalized.title.lower()}|{normalized.occurrences[0].local_date}|{normalized.occurrences[0].local_time}"
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    events.append(normalized)
            self.logger.info("MunicipalRSS: total parsed events=%s", len(events))
            return events
        finally:
            self._close_session()

    def _resolve_rss_urls(self) -> List[str]:
        raw = settings.municipal_rss_urls.strip()
        if not raw:
            return []
        values = [item.strip() for item in raw.split(",")]
        return [value for value in values if value.startswith("http")]

    def _setup_session(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            }
        )

    def _close_session(self) -> None:
        try:
            if self.session is not None:
                self.session.close()
        except Exception:
            pass
        finally:
            self.session = None

    def _fetch_feed_items(self, url: str) -> List[Dict[str, str]]:
        if self.session is None:
            raise RuntimeError("MunicipalRSS session is not initialized")

        timeout = max(settings.municipal_rss_timeout_seconds, 1)
        retries = max(settings.municipal_rss_max_retries, 1)
        last_error: Optional[str] = None
        xml_text: Optional[str] = None

        for attempt in range(1, retries + 1):
            try:
                response = self.session.get(url, timeout=timeout)
                if response.status_code in (429, 500, 502, 503, 504):
                    raise RuntimeError(f"Retryable status={response.status_code}")
                if response.status_code != 200:
                    raise RuntimeError(f"Unexpected status={response.status_code}")
                xml_text = response.text
                break
            except Exception as exc:
                last_error = str(exc)
                self.logger.warning(
                    "MunicipalRSS: feed fetch failed url=%s attempt=%s/%s reason=%s",
                    url,
                    attempt,
                    retries,
                    exc,
                )
                if attempt < retries:
                    time.sleep(float(attempt))

        if not xml_text:
            self.logger.error("MunicipalRSS: all retries failed url=%s last_error=%s", url, last_error)
            return []

        try:
            root = ET.fromstring(xml_text)
        except Exception as exc:
            self.logger.warning("MunicipalRSS: invalid XML url=%s reason=%s", url, exc)
            return []

        items: List[Dict[str, str]] = []
        for item_node in root.findall(".//item"):
            item = {
                "title": self._text(item_node.find("title")),
                "link": self._text(item_node.find("link")),
                "description": self._text(item_node.find("description")),
                "pubDate": self._text(item_node.find("pubDate")),
                "category": self._text(item_node.find("category")),
            }
            items.append(item)
        return items

    def _fetch_source_items(self, url: str) -> List[Dict[str, str]]:
        host = (urlparse(url).hostname or "").lower()
        if "kultur.istanbul" in host:
            return self._fetch_kultur_istanbul_items()
        if "orkestralar.ibb.istanbul" in host:
            return self._fetch_orkestralar_items()
        if "kultursanat.istanbul" in host:
            return self._fetch_kultursanat_items(url)
        if "ataturkkitapligi.ibb.gov.tr" in host:
            return self._fetch_ataturk_kitapligi_items(url)
        return self._fetch_feed_items(url)

    def _fetch_kultur_istanbul_items(self) -> List[Dict[str, str]]:
        event_items = self._fetch_wordpress_items(
            "https://kultur.istanbul/wp-json/wp/v2/event_listing?per_page=50"
        )
        if event_items:
            return event_items
        return self._fetch_wordpress_items("https://kultur.istanbul/wp-json/wp/v2/posts?per_page=30")

    def _fetch_orkestralar_items(self) -> List[Dict[str, str]]:
        return self._fetch_wordpress_items(
            "https://orkestralar.ibb.istanbul/wp-json/wp/v2/posts?per_page=30&categories=1"
        )

    def _fetch_wordpress_items(self, api_url: str) -> List[Dict[str, str]]:
        payload = self._fetch_json(api_url)
        if not isinstance(payload, list):
            return []
        items: List[Dict[str, str]] = []
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            title = self._strip_html(str(entry.get("title", {}).get("rendered", ""))).strip()
            link = str(entry.get("link", "")).strip()
            excerpt = self._strip_html(str(entry.get("excerpt", {}).get("rendered", ""))).strip()
            content = self._strip_html(str(entry.get("content", {}).get("rendered", ""))).strip()
            date_raw = str(entry.get("date_gmt") or entry.get("date") or "").strip()
            post_date = self._parse_pub_date(date_raw)
            event_date = self._extract_wordpress_event_date(entry, content or excerpt, post_date)
            venue = self._extract_wordpress_venue(entry, content)
            if not title or not link.startswith("http") or not date_raw:
                continue
            items.append(
                {
                    "title": title,
                    "link": link,
                    "description": excerpt or content or title,
                    "pubDate": date_raw,
                    "eventDate": event_date.isoformat() if event_date else "",
                    "venue": venue or "",
                    "category": "",
                }
            )
        return items

    def _fetch_kultursanat_items(self, url: str) -> List[Dict[str, str]]:
        html = self._fetch_text(url)
        if not html:
            return []
        items: List[Dict[str, str]] = []
        pattern = re.compile(
            r'href="(?P<link>https://kultursanat\.istanbul/etkinliklerimiz/\d+/[^"]+)".{0,350}?>(?P<title>[^<]+)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        for match in pattern.finditer(html):
            title = self._clean_text(match.group("title"))
            link = self._clean_text(match.group("link"))
            if not title or not link:
                continue
            window = html[match.end() : match.end() + 600]
            venue_match = re.search(
                r'href="https://kultursanat\.istanbul/mekanlarimiz/[^"]+".{0,120}?>([^<]+)</a>',
                window,
                re.IGNORECASE | re.DOTALL,
            )
            date_match = re.search(
                r"(\d{1,2}\s+[A-Za-zÇĞİÖŞÜçğıöşü]+\s+\d{4}).{0,40}?(\d{2}:\d{2})",
                window,
                re.IGNORECASE | re.DOTALL,
            )
            cat_match = re.search(
                r'href="https://kultursanat\.istanbul/etkinliklerimiz/ara\?category_id=\d+".{0,80}?>([^<]+)</a>',
                window,
                re.IGNORECASE | re.DOTALL,
            )
            if not date_match:
                continue
            date_text = f"{self._clean_text(date_match.group(1))} {date_match.group(2)}"
            items.append(
                {
                    "title": title,
                    "link": link,
                    "description": self._clean_text(venue_match.group(1)) if venue_match else title,
                    "pubDate": date_text,
                    "category": self._clean_text(cat_match.group(1)) if cat_match else "",
                }
            )
        return items

    def _fetch_ataturk_kitapligi_items(self, url: str) -> List[Dict[str, str]]:
        html = self._fetch_text(url)
        if not html:
            return []
        items: List[Dict[str, str]] = []
        pattern = re.compile(
            r"(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}).{0,500}?href=\"(?P<link>/tr/Kitaplik/Etkinlikler/[^\"#?]+)\".{0,200}?>(?P<title>[^<]+)</a>",
            re.IGNORECASE | re.DOTALL,
        )
        for match in pattern.finditer(html):
            date_text = self._clean_text(match.group(1))
            link = "https://ataturkkitapligi.ibb.gov.tr" + self._clean_text(match.group("link"))
            title = self._clean_text(match.group("title"))
            if not title:
                continue
            items.append(
                {
                    "title": title,
                    "link": link,
                    "description": title,
                    "pubDate": date_text,
                    "category": "etkinlik",
                }
            )
        return items

    def _fetch_json(self, url: str) -> Optional[object]:
        if self.session is None:
            return None
        timeout = max(settings.municipal_rss_timeout_seconds, 1)
        retries = max(settings.municipal_rss_max_retries, 1)
        for attempt in range(1, retries + 1):
            try:
                response = self.session.get(url, timeout=timeout)
                if response.status_code == 200:
                    return response.json()
                if response.status_code in (429, 500, 502, 503, 504):
                    raise RuntimeError(f"Retryable status={response.status_code}")
                return None
            except Exception as exc:
                self.logger.warning(
                    "MunicipalRSS: json fetch failed url=%s attempt=%s/%s reason=%s",
                    url,
                    attempt,
                    retries,
                    exc,
                )
                if attempt < retries:
                    time.sleep(float(attempt))
        return None

    def _fetch_text(self, url: str) -> str:
        if self.session is None:
            return ""
        timeout = max(settings.municipal_rss_timeout_seconds, 1)
        retries = max(settings.municipal_rss_max_retries, 1)
        for attempt in range(1, retries + 1):
            try:
                response = self.session.get(url, timeout=timeout)
                if response.status_code == 200:
                    return response.text
                if response.status_code in (429, 500, 502, 503, 504):
                    raise RuntimeError(f"Retryable status={response.status_code}")
                return ""
            except Exception as exc:
                self.logger.warning(
                    "MunicipalRSS: text fetch failed url=%s attempt=%s/%s reason=%s",
                    url,
                    attempt,
                    retries,
                    exc,
                )
                if attempt < retries:
                    time.sleep(float(attempt))
        return ""

    def _normalize_item(self, item: Dict[str, str]) -> Optional[NormalizedEvent]:
        title = (item.get("title") or "").strip()
        link = (item.get("link") or "").strip()
        description = (item.get("description") or "").strip()
        if not title or not link.startswith("http"):
            return None

        event_date_source = item.get("eventDate") or item.get("pubDate") or ""
        start_at_utc = self._parse_pub_date(event_date_source)
        if start_at_utc is None:
            return None

        local_date, local_time, timezone_name = DateParser.to_local_parts(start_at_utc)
        city_name = settings.municipal_rss_city_name.strip() or "Istanbul"
        event_type = self._resolve_type(f"{title} {description} {item.get('category') or ''}")

        source = NormalizedSource(
            provider=self.name,
            external_id=self._build_external_id(link),
            title=title,
            source_url=link,
            price=PriceInfo(text="Fiyat bilgisi yok", currency="TRY"),
            ticket_status="unknown",
        )
        occurrence = NormalizedOccurrence(
            start_at_utc=start_at_utc,
            local_date=local_date,
            local_time=local_time,
            timezone=timezone_name,
            venue_name=item.get("venue") or "Resmi Belediye Etkinlik Kaynagi",
            sources=[source],
        )

        return NormalizedEvent(
            title=title,
            description=description[:2000] if description else title,
            type=event_type,
            city_name=city_name,
            image_url=None,
            occurrences=[occurrence],
        )

    def _parse_pub_date(self, value: str) -> Optional[datetime]:
        raw = value.strip()
        if not raw:
            return None
        try:
            if raw.isdigit():
                return datetime.fromisoformat(self._timestamp_to_iso(float(raw)))
            if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
                raw = f"{raw}T00:00:00+03:00"
            if re.match(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}", raw):
                raw = raw.replace(" ", "T", 1)
            if re.match(r"^\d{4}-\d{2}-\d{2}T", raw):
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = self.ISTANBUL_TZ.localize(parsed)
                return parsed.astimezone(pytz.UTC)
        except Exception:
            pass
        tr_parsed = self._parse_turkish_datetime(raw)
        if tr_parsed is not None:
            return tr_parsed
        try:
            parsed = parsedate_to_datetime(raw)
            if parsed.tzinfo is None:
                parsed = self.ISTANBUL_TZ.localize(parsed)
            return parsed.astimezone(pytz.UTC)
        except Exception:
            return None

    def _resolve_type(self, text: str) -> str:
        lower = text.lower()
        for key, mapped in self.CATEGORY_MAP.items():
            if key in lower:
                return mapped
        return "experience"

    def _parse_turkish_datetime(self, value: str) -> Optional[datetime]:
        text = self._clean_text(value.lower())
        m = re.search(r"(\d{1,2})\s+([a-zçğıöşü]+)\s+(\d{4}).{0,20}?(\d{2}:\d{2})", text)
        if not m:
            m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}:\d{2})", text)
            if not m:
                return None
            day = int(m.group(1))
            month = int(m.group(2))
            year = int(m.group(3))
            hour, minute = [int(x) for x in m.group(4).split(":")]
        else:
            day = int(m.group(1))
            month_name = m.group(2)
            month = self.TURKISH_MONTHS.get(month_name)
            if month is None:
                return None
            year = int(m.group(3))
            hour, minute = [int(x) for x in m.group(4).split(":")]
        local_dt = self.ISTANBUL_TZ.localize(datetime(year, month, day, hour, minute))
        return local_dt.astimezone(pytz.UTC)

    def _strip_html(self, value: str) -> str:
        text = re.sub(r"<[^>]+>", " ", value)
        return self._clean_text(text)

    def _clean_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    def _build_external_id(self, link: str) -> str:
        digest = hashlib.sha256(link.encode("utf-8")).hexdigest()[:16]
        return f"rss-{digest}"

    def _extract_wordpress_event_date(
        self,
        entry: Dict[str, Any],
        text: str,
        post_date: Optional[datetime],
    ) -> Optional[datetime]:
        containers = [
            entry,
            entry.get("acf"),
            entry.get("meta"),
            entry.get("event"),
            entry.get("event_listing"),
        ]

        for container in containers:
            if not isinstance(container, dict):
                continue

            combined = self._extract_datetime_field(
                container,
                [
                    "event_start_datetime",
                    "event_start_date_time",
                    "event_start",
                    "start_datetime",
                    "start_date_time",
                    "start_at",
                    "event_start_at",
                ],
            )
            if combined:
                parsed = self._parse_pub_date(combined)
                if parsed:
                    return parsed

            date_value = self._extract_datetime_field(
                container,
                [
                    "event_start_date",
                    "event_date",
                    "start_date",
                    "startDate",
                    "eventStartDate",
                ],
            )
            time_value = self._extract_datetime_field(
                container,
                [
                    "event_start_time",
                    "start_time",
                    "startTime",
                    "eventStartTime",
                    "time",
                ],
            )

            if date_value:
                combined_value = self._combine_date_time(date_value, time_value)
                parsed = self._parse_pub_date(combined_value) if combined_value else None
                if parsed:
                    return parsed

        return self._extract_date_from_content(text, post_date)

    def _extract_wordpress_venue(self, entry: Dict[str, Any], text: str) -> Optional[str]:
        containers = [
            entry,
            entry.get("acf"),
            entry.get("meta"),
            entry.get("event"),
            entry.get("event_listing"),
        ]
        for container in containers:
            if not isinstance(container, dict):
                continue
            value = self._extract_first_value(
                container,
                [
                    "venue",
                    "venue_name",
                    "event_venue",
                    "location",
                    "place",
                    "event_place",
                ],
            )
            if value:
                return value

        match = re.search(
            r"(Mekan|Yer|Salon|Sahne|Venue)\s*[:\-]\s*([^|,\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if match:
            return self._clean_text(match.group(2))
        return None

    def _extract_datetime_from_text(self, text: str) -> Optional[str]:
        if not text:
            return None
        cleaned = self._clean_text(text)
        patterns = [
            r"(\d{1,2}\s+[A-Za-zÃ‡ÄÄ°Ã–ÅÃœÃ§ÄŸÄ±Ã¶ÅŸÃ¼]+\s+\d{4}\s+\d{2}:\d{2})",
            r"(\d{1,2}\s+[A-Za-zÃ‡ÄÄ°Ã–ÅÃœÃ§ÄŸÄ±Ã¶ÅŸÃ¼]+\s+\d{4})",
            r"(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})",
            r"(\d{2}\.\d{2}\.\d{4})",
        ]
        for pattern in patterns:
            match = re.search(pattern, cleaned)
            if match:
                return match.group(1)
        return None

    def _extract_date_from_content(self, text: str, post_date: Optional[datetime]) -> Optional[datetime]:
        if not text:
            return None

        normalized = self._normalize_turkish_text(self._clean_text(text))
        month_map = {
            self._normalize_turkish_text(key): value for key, value in self.TURKISH_MONTHS.items()
        }
        candidates: List[datetime] = []

        range_pattern = re.compile(
            r"(\d{1,2})\s*(?:[-–—/]\s*(\d{1,2})|\s+ve\s+(\d{1,2}))?\s+([a-z]+)(?:\s+(\d{4}))?"
        )
        for match in range_pattern.finditer(normalized):
            day_start = int(match.group(1))
            day_end = match.group(2) or match.group(3)
            month_name = match.group(4)
            year_value = match.group(5)
            month = month_map.get(month_name)
            if not month:
                continue
            year = int(year_value) if year_value else None
            days = [day_start]
            if day_end:
                try:
                    days.append(int(day_end))
                except ValueError:
                    pass
            time_value = self._extract_time_after(normalized, match.end())
            for day in days:
                candidate = self._build_local_datetime(day, month, year, time_value, post_date)
                if candidate:
                    candidates.append(candidate)

        numeric_patterns = [
            re.compile(r"(\d{2})\.(\d{2})\.(\d{4})"),
            re.compile(r"(\d{2})/(\d{2})/(\d{4})"),
        ]
        for pattern in numeric_patterns:
            for match in pattern.finditer(normalized):
                day = int(match.group(1))
                month = int(match.group(2))
                year = int(match.group(3))
                time_value = self._extract_time_after(normalized, match.end())
                candidate = self._build_local_datetime(day, month, year, time_value, post_date)
                if candidate:
                    candidates.append(candidate)

        if not candidates:
            return None

        now_local = datetime.now(self.ISTANBUL_TZ)
        reference = post_date.astimezone(self.ISTANBUL_TZ) if post_date else now_local
        if reference < now_local:
            reference = now_local
        future_candidates = [dt for dt in candidates if dt.date() >= reference.date()]
        if future_candidates:
            future_candidates.sort()
            return future_candidates[0].astimezone(pytz.UTC)

        candidates.sort()
        return candidates[0].astimezone(pytz.UTC)

    def _build_local_datetime(
        self,
        day: int,
        month: int,
        year: Optional[int],
        time_value: Optional[tuple[int, int]],
        post_date: Optional[datetime],
    ) -> Optional[datetime]:
        if year is None:
            reference = post_date.astimezone(self.ISTANBUL_TZ) if post_date else datetime.now(self.ISTANBUL_TZ)
            year = reference.year
            try:
                candidate = datetime(year, month, day)
            except ValueError:
                return None
            if candidate.date() < reference.date():
                year += 1

        hour, minute = time_value if time_value else (0, 0)
        try:
            return self.ISTANBUL_TZ.localize(datetime(year, month, day, hour, minute))
        except ValueError:
            return None

    def _extract_time_after(self, text: str, index: int) -> Optional[tuple[int, int]]:
        window = text[index : index + 32]
        match = re.search(r"(\d{1,2})[:\.](\d{2})", window)
        if not match:
            return None
        hour = int(match.group(1))
        minute = int(match.group(2))
        if hour > 23 or minute > 59:
            return None
        return hour, minute

    def _normalize_turkish_text(self, value: str) -> str:
        text = value.lower()
        return (
            text.replace("\u0131", "i")
            .replace("\u011f", "g")
            .replace("\u00fc", "u")
            .replace("\u015f", "s")
            .replace("\u00f6", "o")
            .replace("\u00e7", "c")
        )

    def _extract_datetime_field(self, container: Dict[str, Any], keys: List[str]) -> Optional[str]:
        value = self._extract_first_value(container, keys)
        if not value:
            return None

        if isinstance(value, (int, float)):
            return self._timestamp_to_iso(value)

        if isinstance(value, dict):
            date_candidate = self._extract_datetime_from_mapping(value)
            if date_candidate:
                return date_candidate

        value_text = str(value).strip()
        if not value_text:
            return None
        return value_text

    def _extract_first_value(self, container: Dict[str, Any], keys: List[str]) -> Optional[str]:
        for key in keys:
            if key not in container:
                continue
            value = container.get(key)
            if isinstance(value, list) and value:
                value = value[0]
            if isinstance(value, dict):
                rendered = value.get("rendered") if "rendered" in value else None
                if rendered:
                    return self._clean_text(str(rendered))
                inner_value = value.get("value")
                if inner_value:
                    return self._clean_text(str(inner_value))
                date_from_map = self._extract_datetime_from_mapping(value)
                if date_from_map:
                    return date_from_map
            if value is None:
                continue
            text = self._clean_text(str(value))
            if text:
                return text
        return None

    def _combine_date_time(self, date_value: str, time_value: Optional[str]) -> Optional[str]:
        date_text = self._clean_text(date_value)
        if not date_text:
            return None

        if time_value:
            time_text = self._clean_text(time_value)
        else:
            time_text = ""

        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_text):
            if time_text:
                return f"{date_text}T{time_text}:00+03:00"
            return f"{date_text}T00:00:00+03:00"

        if time_text and re.match(r"^\d{2}:\d{2}$", time_text):
            return f"{date_text} {time_text}"

        return date_text

    def _extract_datetime_from_mapping(self, value: Dict[str, Any]) -> Optional[str]:
        date_keys = [
            "date",
            "start_date",
            "startDate",
            "event_date",
            "eventDate",
            "start",
            "start_at",
            "startAt",
        ]
        time_keys = [
            "time",
            "start_time",
            "startTime",
            "event_time",
            "eventTime",
        ]

        date_value = self._extract_first_value(value, date_keys)
        time_value = self._extract_first_value(value, time_keys)
        if date_value:
            combined = self._combine_date_time(date_value, time_value)
            if combined:
                return combined

        text_candidates = []
        for item in value.values():
            if isinstance(item, str):
                text_candidates.append(item)
            elif isinstance(item, (int, float)):
                text_candidates.append(str(item))
        if text_candidates:
            return self._extract_datetime_from_text(" ".join(text_candidates))

        return None

    def _timestamp_to_iso(self, value: float) -> str:
        timestamp = float(value)
        if timestamp > 100000000000:
            timestamp /= 1000.0
        return datetime.utcfromtimestamp(timestamp).replace(tzinfo=pytz.UTC).isoformat()

    def _text(self, node: Optional[ET.Element]) -> str:
        if node is None or node.text is None:
            return ""
        return node.text.strip()
