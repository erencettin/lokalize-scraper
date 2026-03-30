"""Parser for ataturkkitapligi.ibb.gov.tr event pages."""

from __future__ import annotations

import re
from typing import List

from providers.municipal_rss.models import RawRssItem, RssFeedSource
from providers.municipal_rss.parsing.base_parser import RssFeedParser
from utils.text_normalizer import clean_text


class AtaturkKitapligiParser(RssFeedParser):
    """Extract event cards from Ataturk library HTML pages."""

    _PATTERN = re.compile(
        r"(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}).{0,500}?href=\"(?P<link>/tr/Kitaplik/Etkinlikler/[^\"#?]+)\".{0,200}?>(?P<title>[^<]+)</a>",
        re.IGNORECASE | re.DOTALL,
    )

    def parse(self, raw_content: str, source: RssFeedSource) -> List[RawRssItem]:
        html = raw_content or ""
        items: List[RawRssItem] = []
        for match in self._PATTERN.finditer(html):
            title = clean_text(match.group("title"))
            if not title:
                continue
            link = "https://ataturkkitapligi.ibb.gov.tr" + clean_text(match.group("link"))
            items.append(
                RawRssItem(
                    title=title,
                    link=link,
                    description=title,
                    pub_date=clean_text(match.group(1)),
                    category="etkinlik",
                )
            )
        return items
