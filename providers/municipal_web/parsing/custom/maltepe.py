"""News card parser for Maltepe Belediyesi."""

from __future__ import annotations

import re
from typing import List
from urllib.parse import urljoin

from providers.municipal_web.constants import MAX_BODY_TEXT_LENGTH
from providers.municipal_web.models import MunicipalSite, RawEventItem
from providers.municipal_web.parsing.base_strategy import SiteParser
from utils.html_extractor import extract_body_text, extract_title
from utils.text_normalizer import clean_text, strip_html


class MaltepeParser(SiteParser):
    """Parse Maltepe newsBox card structures and fallback links."""

    def parse_list(self, html: str, site: MunicipalSite) -> List[RawEventItem]:
        items = self._parse_news_cards(html, site)
        return items if items else self._parse_fallback_links(html, site)

    def parse_detail(self, html: str, item: RawEventItem, site: MunicipalSite) -> RawEventItem:
        item.title = item.title or extract_title(html)
        item.description = extract_body_text(html, MAX_BODY_TEXT_LENGTH)
        item.venue = item.venue or site.name
        item.link = item.link or site.base_url
        return item

    def _parse_news_cards(self, html: str, site: MunicipalSite) -> List[RawEventItem]:
        card_pattern = re.compile(
            r'<div[^>]*class="[^"]*newsBox[^"]*"[^>]*>.*?<a[^>]*href="(?P<link>[^"]+)"[^>]*>.*?'
            r'<small[^>]*>(?P<date>[^<]+)</small>.*?<h3[^>]*>(?P<title>[^<]+)</h3>.*?'
            r'<p[^>]*class="[^"]*newsDescription[^"]*"[^>]*>(?P<desc>.*?)</p>',
            re.IGNORECASE | re.DOTALL,
        )
        items: List[RawEventItem] = []
        for match in card_pattern.finditer(html):
            items.append(
                RawEventItem(
                    title=clean_text(match.group("title")),
                    date=clean_text(match.group("date")),
                    link=urljoin(site.base_url, match.group("link")),
                    description=strip_html(match.group("desc")),
                    venue=site.name,
                )
            )
        return items

    def _parse_fallback_links(self, html: str, site: MunicipalSite) -> List[RawEventItem]:
        links = re.finditer(r'href="(?P<link>/(?:tr/)?guncel/etkinlikler/[^"#?]+)"', html, re.IGNORECASE)
        return [RawEventItem(link=urljoin(site.base_url, match.group("link"))) for match in links]
