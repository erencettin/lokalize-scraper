import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Set
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
            if not title or not link.startswith("http") or not date_raw:
                continue
            items.append(
                {
                    "title": title,
                    "link": link,
                    "description": excerpt or content or title,
                    "pubDate": date_raw,
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

        start_at_utc = self._parse_pub_date(item.get("pubDate") or "")
        if start_at_utc is None:
            return None

        local_date, local_time, timezone_name = DateParser.to_local_parts(start_at_utc)
        city_name = settings.municipal_rss_city_name.strip() or "Istanbul"
        event_type = self._resolve_type(f"{title} {description} {item.get('category') or ''}")

        source = NormalizedSource(
            provider=self.name,
            external_id=f"rss-{hash(link)}",
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
            venue_name="Resmi Belediye Etkinlik Kaynagi",
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

    def _text(self, node: Optional[ET.Element]) -> str:
        if node is None or node.text is None:
            return ""
        return node.text.strip()
