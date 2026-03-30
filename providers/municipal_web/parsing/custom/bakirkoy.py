"""Line-oriented parser for Bakırköy Belediyesi pages."""

from __future__ import annotations

import re
from typing import List

from providers.municipal_web.constants import MAX_BODY_TEXT_LENGTH
from providers.municipal_web.models import MunicipalSite, RawEventItem
from providers.municipal_web.parsing.base_strategy import SiteParser
from utils.html_extractor import extract_body_text, extract_first_image_url, extract_title
from utils.text_normalizer import clean_text


class BakirkoyParser(SiteParser):
    """Parse text-line sections where category and date share a line."""

    def parse_list(self, html: str, site: MunicipalSite) -> List[RawEventItem]:
        text = re.sub(r"<[^>]+>", "\n", html or "")
        lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
        category_re = re.compile(r"^(Konser|Söyleşi|Tiyatro|Sergi|Sinema|Atölye|Festival|Müzik|Diğer)\s*\|\s*(?P<date>.+)$", re.IGNORECASE)
        items: List[RawEventItem] = []
        for idx, line in enumerate(lines):
            match = category_re.match(line)
            if not match:
                continue
            parsed = self._parse_line(lines, idx, match, html, site)
            if parsed is not None:
                items.append(parsed)
        return items

    def parse_detail(self, html: str, item: RawEventItem, site: MunicipalSite) -> RawEventItem:
        item.title = item.title or extract_title(html)
        item.description = item.description or extract_body_text(html, MAX_BODY_TEXT_LENGTH)
        item.image_url = item.image_url or extract_first_image_url(html, site.base_url)
        item.link = item.link or site.base_url
        item.venue = item.venue or site.name
        return item

    def _parse_line(self, lines: List[str], index: int, match: re.Match[str], html: str, site: MunicipalSite) -> RawEventItem | None:
        category = clean_text(match.group(1))
        if category.lower() == "diğer":
            return None
        title = self._find_title(lines, index)
        date_line = clean_text(match.group("date"))
        date_match = re.search(r"(\d{1,2}\s+[A-Za-zÇĞİÖŞÜçğıöşü]+\s+\d{4})", date_line)
        if not title or not date_match:
            return None
        time_match = re.search(r"(\d{1,2}[:\.]\d{2})", date_line)
        return RawEventItem(
            title=title,
            link=site.base_url,
            venue=site.name,
            date=date_match.group(1),
            time=(time_match.group(1).replace(".", ":") if time_match else ""),
            description=f"{category} {title}".strip(),
            image_url=extract_first_image_url(html, site.base_url),
        )

    def _find_title(self, lines: List[str], index: int) -> str:
        blocked = {"TÜM ETKİNLİKLERİMİZ", "BAKIRKÖY'DE BU HAFTA", "ETKİNLİKLERİMİZ"}
        for offset in range(1, 4):
            if index + offset >= len(lines):
                break
            candidate = clean_text(lines[index + offset]).lstrip("# ").strip()
            if candidate and candidate.upper() not in blocked:
                return candidate
        return ""
