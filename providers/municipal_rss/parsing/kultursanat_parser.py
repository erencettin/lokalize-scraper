"""Parser for kultursanat.istanbul HTML listing pages."""

from __future__ import annotations

import re
from typing import List, Optional

from providers.municipal_rss.constants import CONTENT_SEARCH_WINDOW
from providers.municipal_rss.models import RawRssItem, RssFeedSource
from providers.municipal_rss.parsing.base_parser import RssFeedParser
from utils.text_normalizer import clean_text


class KultursanatParser(RssFeedParser):
    """Extract events from kultursanat.istanbul markup."""

    _CARD_RE = re.compile(
        r'href="(?P<link>https://kultursanat\.istanbul/etkinliklerimiz/\d+/[^"]+)".{0,350}?>(?P<title>[^<]+)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    def parse(self, raw_content: str, source: RssFeedSource) -> List[RawRssItem]:
        html = raw_content or ""
        items: List[RawRssItem] = []
        for match in self._CARD_RE.finditer(html):
            item = self._build_item(match, html)
            if item is not None:
                items.append(item)
        return items

    def _build_item(self, match: re.Match[str], html: str) -> Optional[RawRssItem]:
        title = clean_text(match.group("title"))
        link = clean_text(match.group("link"))
        if not title or not link:
            return None
        window = html[match.end() : match.end() + CONTENT_SEARCH_WINDOW]
        date_match = re.search(r"(\d{1,2}\s+[A-Za-zÇĞİÖŞÜçğıöşü]+\s+\d{4}).{0,40}?(\d{2}:\d{2})", window, re.IGNORECASE | re.DOTALL)
        if not date_match:
            return None
        venue = self._extract(r'href="https://kultursanat\.istanbul/mekanlarimiz/[^"]+".{0,120}?>([^<]+)</a>', window)
        category = self._extract(r'href="https://kultursanat\.istanbul/etkinliklerimiz/ara\?category_id=\d+".{0,80}?>([^<]+)</a>', window)
        date_text = f"{clean_text(date_match.group(1))} {date_match.group(2)}"
        return RawRssItem(title=title, link=link, description=venue or title, pub_date=date_text, category=category)

    def _extract(self, pattern: str, text: str) -> str:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        return clean_text(match.group(1)) if match else ""
