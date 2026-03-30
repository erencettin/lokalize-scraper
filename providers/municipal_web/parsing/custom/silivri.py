"""Custom parser for Silivri Belediyesi."""

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


class SilivriParser(SiteParser):
    """Parse Silivri links and detail metadata fields."""

    def parse_list(self, html: str, site: MunicipalSite) -> List[RawEventItem]:
        links = set()
        for pattern in (r'href="(?P<link>https?://kultursanat\.silivri\.bel\.tr/etkinlik/\d+/\d+)"', r'href="(?P<link>/etkinlik/\d+/\d+)"'):
            for match in re.finditer(pattern, html, re.IGNORECASE):
                links.add(urljoin(site.base_url, match.group("link")))
        return [RawEventItem(link=link) for link in sorted(links)]

    def parse_detail(self, html: str, item: RawEventItem, site: MunicipalSite) -> RawEventItem:
        item.title = extract_title(html) or item.title
        category = extract_label_value(html, ["Etkinlik Türü", "Kategori"])
        item.venue = extract_label_value(html, ["Etkinlik Mekanı", "Yer", "Mekan"]) or item.venue or site.name
        item.date = item.date or extract_label_value(html, ["Etkinlik Tarihi", "Tarih"])
        item.time = item.time or extract_label_value(html, ["Etkinlik Saati", "Saat"])
        if not item.date:
            item.date, block_time = extract_date_time_block(html)
            item.time = item.time or block_time
        item.description = extract_body_text(html, MAX_BODY_TEXT_LENGTH) or item.description
        if category and category.lower() not in item.description.lower():
            item.description = f"{category} {item.description}".strip()
        item.image_url = item.image_url or extract_first_image_url(html, site.base_url)
        return item
