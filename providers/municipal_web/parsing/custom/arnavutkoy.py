"""Custom parser for Arnavutköy Belediyesi."""

from __future__ import annotations

import re
from typing import List
from urllib.parse import urljoin

from providers.municipal_web.constants import MAX_BODY_TEXT_LENGTH
from providers.municipal_web.models import MunicipalSite, RawEventItem
from providers.municipal_web.parsing.base_strategy import SiteParser
from utils.html_extractor import (
    extract_body_text,
    extract_date_time_block,
    extract_first_image_url,
    extract_label_value,
    extract_title,
)


class ArnavutkoyParser(SiteParser):
    """Parse list/detail pages for Arnavutköy event pages."""

    def parse_list(self, html: str, site: MunicipalSite) -> List[RawEventItem]:
        links = set()
        patterns = (
            r'href="(?P<link>https?://(?:www\.)?arnavutkoy\.bel\.tr/etkinlik/[^"#?]+)"',
            r'href="(?P<link>/etkinlik/[^"#?]+)"',
        )
        for pattern in patterns:
            for match in re.finditer(pattern, html, re.IGNORECASE):
                links.add(urljoin(site.base_url, match.group("link")))
        return [RawEventItem(link=link) for link in sorted(links)]

    def parse_detail(self, html: str, item: RawEventItem, site: MunicipalSite) -> RawEventItem:
        item.title = item.title or extract_title(html)
        item.venue = item.venue or extract_label_value(html, ["Etkinlik NEREDE", "Etkinlik Nerede", "Yer", "Mekan"]) or site.name
        item.date = item.date or extract_label_value(html, ["Etkinlik TARİHİ", "Etkinlik Tarihi", "Tarih"])
        item.time = item.time or extract_label_value(html, ["Etkinlik SAATİ", "Etkinlik Saati", "Saat"])
        if not item.date:
            item.date, item.time = extract_date_time_block(html)
        item.description = item.description or extract_body_text(html, MAX_BODY_TEXT_LENGTH)
        item.image_url = item.image_url or extract_first_image_url(html, site.base_url)
        return item
