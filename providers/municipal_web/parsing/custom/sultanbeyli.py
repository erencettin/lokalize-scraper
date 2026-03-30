"""Custom block parser for Sultanbeyli Belediyesi."""

from __future__ import annotations

import re
from datetime import datetime
from typing import List

import pytz

from providers.municipal_web.constants import ISTANBUL_TIMEZONE, MAX_BODY_TEXT_LENGTH
from providers.municipal_web.models import MunicipalSite, RawEventItem
from providers.municipal_web.parsing.base_strategy import SiteParser
from utils.html_extractor import (
    extract_body_text,
    extract_date_time_block,
    extract_label_value,
    extract_title,
)
from utils.text_normalizer import clean_text, strip_html


class SultanbeyliParser(SiteParser):
    """Parse Sultanbeyli event blocks with month short names."""

    MONTH_MAP = {
        "oca": "Ocak",
        "şub": "Şubat",
        "sub": "Şubat",
        "mar": "Mart",
        "nis": "Nisan",
        "may": "Mayıs",
        "haz": "Haziran",
        "tem": "Temmuz",
        "ağu": "Ağustos",
        "agu": "Ağustos",
        "eyl": "Eylül",
        "eki": "Ekim",
        "kas": "Kasım",
        "ara": "Aralık",
    }

    def parse_list(self, html: str, site: MunicipalSite) -> List[RawEventItem]:
        items = [item for item in (self._parse_block(match) for match in self._block_pattern().finditer(html)) if item]
        return items if items else self._parse_fallback_links(html)

    def parse_detail(self, html: str, item: RawEventItem, site: MunicipalSite) -> RawEventItem:
        item.title = extract_title(html) or item.title
        item.venue = extract_label_value(html, ["Yer", "Mekan", "Adres"]) or item.venue or site.name
        item.date, item.time = extract_date_time_block(html) if not item.date else (item.date, item.time)
        item.description = extract_body_text(html, MAX_BODY_TEXT_LENGTH) or item.description
        return item

    def _parse_block(self, match: re.Match[str]) -> RawEventItem | None:
        day = clean_text(match.group(1))
        month_raw = clean_text(match.group(2)).lower()[:3]
        month = self.MONTH_MAP.get(month_raw, clean_text(match.group(2)))
        title = clean_text(strip_html(match.group(8))).lstrip("* ").strip() or clean_text(strip_html(match.group(7)))
        if not title:
            return None
        block_text = clean_text(strip_html(match.group(0)))
        return RawEventItem(
            title=title,
            date=f"{day} {month} {self._resolve_year(block_text)}",
            time=clean_text(match.group(5)).replace(".", ":"),
            venue=clean_text(strip_html(match.group(6))),
            link=clean_text(match.group(3)),
            description=title,
            image_url=self._extract_image(match.group(0)),
        )

    def _resolve_year(self, text: str) -> int:
        match = re.search(r"\b(20\d{2})\b", text)
        if match:
            return int(match.group(1))
        return datetime.now(pytz.timezone(ISTANBUL_TIMEZONE)).year

    def _extract_image(self, html_block: str) -> str:
        match = re.search(r'<img[^>]*src="([^"]+)"', html_block, re.IGNORECASE | re.DOTALL)
        return clean_text(match.group(1)) if match else ""

    def _parse_fallback_links(self, html: str) -> List[RawEventItem]:
        links = re.findall(r'href="(https?://[^"]*(?:/event/|/etkinlik/)[^"]+)"', html, re.IGNORECASE)
        return [RawEventItem(link=link) for link in links]

    def _block_pattern(self) -> re.Pattern[str]:
        return re.compile(
            r'<div class="ovaev-content">.*?<div class="date-event">.*?<span class="date">\s*(\d{1,2})\s*</span>.*?'
            r'<span class="month">\s*([A-Za-zÇĞİÖŞÜçğıöşü]+)\s*</span>.*?<a href="(https?://[^"]+/etkinlik/[^"]+)"[^>]*>.*?'
            r'<div class="time equal-date">.*?<span class="time-date-child">.*?(?:<span class="date-child">\s*([^<]+)\s*</span>.*?)?'
            r'<span>\s*(\d{1,2}:\d{2})\s*</span>.*?<div class="venue">.*?<span class="number">\s*(.*?)\s*</span>.*?'
            r'<h2 class="[^"]*event_title[^"]*">.*?<a[^>]*title="([^"]+)"[^>]*>(.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
