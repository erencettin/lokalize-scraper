"""Reusable HTML extraction helpers."""

from __future__ import annotations

import re
from typing import List, Tuple
from urllib.parse import urljoin

from utils.text_normalizer import clean_text, strip_html


def extract_title(html: str) -> str:
    """Extract event title from H1 first, then document title."""
    h1_match = re.search(r"<h1[^>]*>([^<]+)</h1>", html or "", re.IGNORECASE)
    if h1_match:
        return clean_text(h1_match.group(1))
    title_match = re.search(r"<title[^>]*>([^<]+)</title>", html or "", re.IGNORECASE)
    return clean_text(title_match.group(1)) if title_match else ""


def extract_label_value(html: str, labels: List[str]) -> str:
    """Extract first matching Label: Value text from page content."""
    text = _line_text(html)
    for label in labels:
        pattern = re.compile(rf"{re.escape(label)}\s*[:\-]\s*(.+)$", re.IGNORECASE | re.MULTILINE)
        match = pattern.search(text)
        if match:
            return clean_text(match.group(1))
    return ""


def extract_body_text(html: str, max_length: int) -> str:
    """Extract and trim body text with a max length guard."""
    text = strip_html(html)
    if len(text) <= max_length:
        return text
    return f"{text[:max_length].rstrip()}..."


def extract_first_image_url(html: str, base_url: str) -> str:
    """Extract first image URL and convert it to absolute URL."""
    match = re.search(r'<img[^>]*src="([^"]+)"', html or "", re.IGNORECASE)
    if not match:
        return ""
    return urljoin(base_url, clean_text(match.group(1)))


def extract_date_time_block(html: str) -> Tuple[str, str]:
    """Extract date-time pair from free text blocks in HTML."""
    text = strip_html(html)
    long_date_match = re.search(
        r"(\d{1,2}\s+[A-Za-zçğıöşüÇĞİÖŞÜ]+[, ]+\s*\d{4}).{0,50}?(\d{1,2}[:\.]\d{2})",
        text,
        re.IGNORECASE,
    )
    if long_date_match:
        return clean_text(long_date_match.group(1)), long_date_match.group(2).replace(".", ":")

    dotted_date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", text)
    if dotted_date_match:
        return clean_text(dotted_date_match.group(1)), ""

    return "", ""


def _line_text(html: str) -> str:
    with_breaks = re.sub(r"</?(?:div|p|li|br|tr|td|th|h\d|span)[^>]*>", "\n", html or "", flags=re.IGNORECASE)
    plain = re.sub(r"<[^>]+>", " ", with_breaks)
    lines = [clean_text(line) for line in plain.splitlines() if clean_text(line)]
    return "\n".join(lines)
