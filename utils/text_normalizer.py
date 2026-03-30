"""Text normalization helpers shared across providers and services."""

from __future__ import annotations

import html as html_module
import re
import unicodedata


def clean_text(value: str) -> str:
    """Collapse whitespace and trim leading/trailing blanks."""
    decoded = html_module.unescape(value or "")
    return re.sub(r"\s+", " ", decoded).strip()


def strip_html(value: str) -> str:
    """Remove HTML tags and return normalized plain text."""
    return clean_text(re.sub(r"<[^>]+>", " ", value or ""))


def _fix_mojibake(text: str) -> str:
    if not text or ("\u00c3" not in text and "\u00c4" not in text and "\u00c5" not in text):
        return text
    try:
        return text.encode("latin1").decode("utf-8")
    except UnicodeError:
        return text


class TextNormalizer:
    """Backward-compatible normalization utilities for matching logic."""

    @staticmethod
    def normalize_for_match(text: str) -> str:
        if not text:
            return ""

        normalized = _fix_mojibake(text).lower().strip()
        normalized = (
            normalized.replace("\u0131", "i")
            .replace("\u0307", "")
            .replace("\u011f", "g")
            .replace("\u00fc", "u")
            .replace("\u015f", "s")
            .replace("\u00f6", "o")
            .replace("\u00e7", "c")
        )
        normalized = "".join(
            char for char in unicodedata.normalize("NFD", normalized) if unicodedata.category(char) != "Mn"
        )
        normalized = re.sub(r"[^\w\s]", "", normalized)
        return clean_text(normalized)

    @staticmethod
    def generate_logical_key(title: str, city: str) -> str:
        norm_title = TextNormalizer.normalize_for_match(title).replace(" ", "-")
        norm_city = TextNormalizer.normalize_for_match(city).replace(" ", "-")
        return f"{norm_title}-{norm_city}"

    @staticmethod
    def generate_fingerprint(title: str, venue: str, local_date: str, local_time: str) -> str:
        norm_title = TextNormalizer.normalize_for_match(title)
        norm_venue = TextNormalizer.normalize_for_match(venue)
        return f"{norm_title}|{norm_venue}|{local_date}|{local_time}"
