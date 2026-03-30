"""Generic HTML anchor/card parser strategy."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import unquote, urljoin, urlparse

from providers.municipal_web.constants import EVENT_KEYWORDS
from providers.municipal_web.models import MunicipalSite, RawEventItem
from providers.municipal_web.parsing.base_strategy import SiteParser
from providers.municipal_web.parsing.label_detail_strategy import LabelDetailStrategy
from utils.html_extractor import extract_date_time_block, extract_first_image_url
from utils.text_normalizer import clean_text, strip_html


@dataclass
class HtmlCardStrategy(SiteParser):
    """Extract event cards from HTML by regex link patterns."""

    card_patterns: List[str]
    detail_strategy: Optional[SiteParser] = None
    require_keywords: bool = True

    def parse_list(self, html: str, site: MunicipalSite) -> List[RawEventItem]:
        items: List[RawEventItem] = []
        seen_links: set[str] = set()
        for pattern in self.card_patterns:
            items.extend(self._parse_pattern(html, site, pattern, seen_links))
        return items

    def parse_detail(self, html: str, item: RawEventItem, site: MunicipalSite) -> RawEventItem:
        strategy = self.detail_strategy or LabelDetailStrategy()
        return strategy.parse_detail(html, item, site)

    def _parse_pattern(self, html: str, site: MunicipalSite, pattern: str, seen_links: set[str]) -> List[RawEventItem]:
        items: List[RawEventItem] = []
        for match in re.finditer(pattern, html, re.IGNORECASE | re.DOTALL):
            item = self._build_item_from_match(match, html, site, seen_links)
            if item:
                items.append(item)
        return items

    def _build_item_from_match(
        self, match: re.Match[str], html: str, site: MunicipalSite, seen_links: set[str]
    ) -> Optional[RawEventItem]:
        link = clean_text(match.groupdict().get("link", ""))
        absolute_link = urljoin(site.base_url, link)
        if not link or absolute_link in seen_links:
            return None
        seen_links.add(absolute_link)

        raw_body = match.groupdict().get("body", "")
        title = self._extract_title(raw_body, match.group(0), absolute_link)
        if not title or not self._is_allowed(title, raw_body, absolute_link):
            return None
        date_text, time_text = self._extract_date_time(raw_body, match.group(0))
        return RawEventItem(
            title=title,
            link=absolute_link,
            venue=site.name,
            date=date_text,
            time=time_text,
            description=strip_html(raw_body) or title,
            image_url=extract_first_image_url(raw_body or html, site.base_url),
        )

    def _extract_title(self, raw_body: str, full_match: str, absolute_link: str) -> str:
        body_title = clean_text(strip_html(raw_body))
        if body_title and body_title.lower() not in {"detay", "daha fazla"}:
            return body_title
        attribute_title = self._extract_attribute_title(full_match)
        if attribute_title:
            return attribute_title
        return self._title_from_link(absolute_link)

    def _extract_attribute_title(self, full_match: str) -> str:
        for attr in ("title", "aria-label", "data-title"):
            match = re.search(fr'{attr}="([^"]+)"', full_match, re.IGNORECASE)
            if match:
                cleaned = clean_text(strip_html(match.group(1)))
                if cleaned:
                    return cleaned
        return ""

    def _title_from_link(self, absolute_link: str) -> str:
        path = unquote(urlparse(absolute_link).path.strip("/"))
        slug = path.split("/")[-1] if path else ""
        slug = re.sub(r"^\d+[-_/]*", "", slug)
        return clean_text(slug.replace("-", " ").replace("_", " "))

    def _is_allowed(self, title: str, raw_body: str, absolute_link: str) -> bool:
        return not self.require_keywords or self._contains_event_keywords(f"{title} {raw_body} {absolute_link}")

    def _extract_date_time(self, raw_body: str, full_match: str) -> tuple[str, str]:
        date_text, time_text = extract_date_time_block(raw_body)
        return (date_text, time_text) if date_text else extract_date_time_block(full_match)

    def _contains_event_keywords(self, value: str) -> bool:
        lowered = clean_text(value).lower()
        return any(keyword in lowered for keyword in EVENT_KEYWORDS)
