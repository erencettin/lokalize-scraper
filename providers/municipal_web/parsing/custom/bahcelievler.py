"""Single-page parser for Bahçelievler Belediyesi."""

from __future__ import annotations

import re
from typing import List

from providers.municipal_web.constants import MAX_BODY_TEXT_LENGTH
from providers.municipal_web.models import MunicipalSite, RawEventItem
from providers.municipal_web.parsing.base_strategy import SiteParser
from utils.html_extractor import extract_body_text, extract_first_image_url, extract_label_value, extract_title
from utils.text_normalizer import strip_html


class BahcelievlerParser(SiteParser):
    """Extract a single event directly from one static page."""

    def parse_list(self, html: str, site: MunicipalSite) -> List[RawEventItem]:
        title = extract_title(html)
        text = strip_html(html)
        date_match = re.search(
            r"(\d{1,2}\s+[A-Za-zÇĞİÖŞÜçğıöşü]+\s+\d{4})(?:\s+(\d{1,2}[:\.]\d{2}))?",
            text,
            re.IGNORECASE,
        )
        if not title or not date_match:
            return []
        return [
            RawEventItem(
                title=title,
                link=site.base_url,
                venue=extract_label_value(html, ["Yer", "Mekan", "Etkinlik Alanı"]) or site.name,
                date=date_match.group(1),
                time=(date_match.group(2) or "").replace(".", ":"),
                description=extract_body_text(html, MAX_BODY_TEXT_LENGTH),
                image_url=extract_first_image_url(html, site.base_url),
            )
        ]

    def parse_detail(self, html: str, item: RawEventItem, site: MunicipalSite) -> RawEventItem:
        item.title = item.title or extract_title(html)
        item.description = item.description or extract_body_text(html, MAX_BODY_TEXT_LENGTH)
        item.image_url = item.image_url or extract_first_image_url(html, site.base_url)
        item.link = item.link or site.base_url
        item.venue = item.venue or site.name
        return item
