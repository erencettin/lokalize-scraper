"""Table parser for Kartal Belediyesi calendar pages."""

from __future__ import annotations

import re
from typing import List
from urllib.parse import urljoin

from providers.municipal_web.constants import MAX_BODY_TEXT_LENGTH
from providers.municipal_web.models import MunicipalSite, RawEventItem
from providers.municipal_web.parsing.base_strategy import SiteParser
from utils.html_extractor import extract_body_text, extract_title
from utils.text_normalizer import clean_text, strip_html


class KartalParser(SiteParser):
    """Parse paired date/event rows from Kartal event tables."""

    def parse_list(self, html: str, site: MunicipalSite) -> List[RawEventItem]:
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.IGNORECASE | re.DOTALL)
        if len(rows) < 2:
            return []
        items: List[RawEventItem] = []
        for index in range(len(rows) - 1):
            items.extend(self._parse_row_pair(rows[index], rows[index + 1], site))
        return items

    def parse_detail(self, html: str, item: RawEventItem, site: MunicipalSite) -> RawEventItem:
        item.title = item.title or extract_title(html)
        item.description = item.description or extract_body_text(html, MAX_BODY_TEXT_LENGTH)
        item.link = item.link or site.base_url
        item.venue = item.venue or site.name
        return item

    def _parse_row_pair(self, header_row: str, event_row: str, site: MunicipalSite) -> List[RawEventItem]:
        header_dates = [clean_text(strip_html(cell)) for cell in re.findall(r"<td[^>]*>(.*?)</td>", header_row, re.IGNORECASE | re.DOTALL)]
        if len(header_dates) != 7 or "Etkinlik Bulunmamaktad" in event_row:
            return []
        cells = re.findall(r"<td[^>]*>(.*?)</td>", event_row, re.IGNORECASE | re.DOTALL)
        if len(cells) != 7:
            return []
        items: List[RawEventItem] = []
        for date_text, cell_html in zip(header_dates, cells):
            items.extend(self._parse_cell(clean_text(date_text), cell_html, site))
        return items

    def _parse_cell(self, date_text: str, cell_html: str, site: MunicipalSite) -> List[RawEventItem]:
        if not date_text:
            return []
        anchors = re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', cell_html, re.IGNORECASE | re.DOTALL)
        items: List[RawEventItem] = []
        for href, raw_title in anchors:
            title = clean_text(strip_html(raw_title)).lstrip("* ").strip()
            if not title or "rezervasyon" in title.lower():
                continue
            items.append(
                RawEventItem(
                    title=title,
                    venue=site.name,
                    date=date_text,
                    link="https://www.kartal.bel.tr/KulturSanat/EtkinlikTakvimi",
                    image_url=urljoin(site.base_url, href),
                    description=title,
                )
            )
        return items
