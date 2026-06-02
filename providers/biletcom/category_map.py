"""Maps Bilet.com category strings to internal event type IDs."""
from __future__ import annotations

import re
import unicodedata
from typing import List, Optional


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# Bilet.com activity.categories[] values → internal type
_CATEGORY_MAP: dict[str, str] = {
    "aktivite":        "activity",
    "aktiviteler":     "activity",
    "eglence":         "activity",
    "egitim":          "workshop",
    "atölye":          "workshop",
    "atolye":          "workshop",
    "konser":          "concert",
    "muzik":           "concert",
    "müzik":           "concert",
    "tiyatro":         "theatre",
    "sahne":           "theatre",
    "dans":            "theatre",
    "opera":           "theatre",
    "müzikal":         "theatre",
    "muzikal":         "theatre",
    "gösteri":         "theatre",
    "gosteri":         "theatre",
    "stand-up":        "standup",
    "standup":         "standup",
    "stand up":        "standup",
    "festival":        "festival",
    "spor":            "match",
    "sinema":          "cinema",
    "sergi":           "exhibition",
    "müze":            "exhibition",
    "muze":            "exhibition",
}

# Keywords searched in title/slug to infer type when categories[] is empty or unknown.
_TITLE_KEYWORDS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(konser|konserl|concert|fest|festival|live)\b"), "concert"),
    (re.compile(r"\b(tiyatro|sahne|opera|bale|dans|musical|müzikal)\b"), "theatre"),
    (re.compile(r"\b(stand.?up|standup|komedi)\b"), "standup"),
    (re.compile(r"\b(maç|mac|futbol|basketbol|spor|voleybol)\b"), "match"),
    (re.compile(r"\b(akvaryum|aquarium|hayvanat|zoo)\b"), "activity"),
    (re.compile(r"\b(teleferik|zipline|macera|park|tematik|tema)\b"), "activity"),
    (re.compile(r"\b(müze|muze|museum|sergi|galeri)\b"), "exhibition"),
    (re.compile(r"\b(tur|tour|gezi|tekne|bogaz|boğaz|ada)\b"), "activity"),
    (re.compile(r"\b(havuz|yüzme|yuzme)\b"), "activity"),
    (re.compile(r"\b(seyir|kule|terrace|skyview|sky view)\b"), "activity"),
    (re.compile(r"\b(workshop|atolye|atölye|egitim|eğitim|seminer)\b"), "workshop"),
    (re.compile(r"\b(sinema|film|cinema|movie)\b"), "cinema"),
]


def resolve(categories: List[str], title: str = "", slug: str = "") -> str:
    """Return the internal type string for a Bilet.com activity.

    Resolution order:
    1. activity.categories[] direct lookup
    2. Title / slug keyword scan
    3. Default → "activity" (Bilet.com's core offering is experience venues)
    """
    for raw in categories:
        key = _normalize(raw)
        if key in _CATEGORY_MAP:
            return _CATEGORY_MAP[key]

    combined = _normalize(f"{title} {slug}")
    for pattern, type_id in _TITLE_KEYWORDS:
        if pattern.search(combined):
            return type_id

    return "activity"
