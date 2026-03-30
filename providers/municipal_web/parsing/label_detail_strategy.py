"""Detail parser extracting common Label:Value fields from HTML."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

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


@dataclass
class LabelDetailStrategy(SiteParser):
    """Fill event detail by scanning commonly-used Turkish labels."""

    label_map: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "venue": ["Yer", "Mekan", "Konum", "Adres"],
            "date": ["Tarih", "Etkinlik Tarihi"],
            "time": ["Saat", "Etkinlik Saati"],
            "description": ["Açıklama", "Detay"],
        }
    )

    def parse_list(self, html: str, site: MunicipalSite) -> List[RawEventItem]:
        return []

    def parse_detail(self, html: str, item: RawEventItem, site: MunicipalSite) -> RawEventItem:
        item.title = item.title or extract_title(html)
        item.venue = item.venue or extract_label_value(html, self.label_map["venue"]) or site.name
        item.date = item.date or extract_label_value(html, self.label_map["date"])
        item.time = item.time or extract_label_value(html, self.label_map["time"])

        if not item.date:
            item.date, block_time = extract_date_time_block(html)
            item.time = item.time or block_time

        text_description = extract_label_value(html, self.label_map["description"])
        item.description = item.description or text_description or extract_body_text(html, MAX_BODY_TEXT_LENGTH)
        item.image_url = item.image_url or extract_first_image_url(html, site.base_url)
        item.link = item.link or site.base_url
        return item
