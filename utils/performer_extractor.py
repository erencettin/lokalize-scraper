"""Infer performer/artist name from event titles.

Only applies when there is no structured performer field from the provider API.
Returns None whenever the extraction is ambiguous or the title appears generic.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

_PAREN_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")
_YEAR_OR_ANNIVERSARY_RE = re.compile(r"\b\d{4}\b|\b\d+\.\s*y[iı]l\b", re.IGNORECASE)

# Ordered from most specific to least — first match wins.
_ALL_SUFFIXES = (
    # Stand-up / comedy
    " stand up",
    " stand-up",
    " standup",
    " komedi gösterisi",
    " komedi show",
    " one man show",
    # Concert / music
    " gala konseri",
    " özel gala",
    " gala",
    " konseri",
    " concert",
    " canlı performans",
    " canli performans",
    " akustik",
    " turnesi",
    " tour",
    " live",
    # Theatre / performing arts
    " tiyatrosu",
    " müzikali",
    " müzikal",
    " operası",
    " balesi",
    " gösterisi",
    " performansı",
    " resitali",
    # Exhibition / visual arts
    " sergisi",
    " retrospektifi",
    # Workshop / educational
    " atölyesi",
    " workshopu",
    " masterclassı",
    # Kids / family
    " çocuk tiyatrosu",
    # NOTE: " oyunu" intentionally omitted — too broad, matches non-performer titles
    # (e.g. "Mangala Oyunu", "Yönetim Oyunu")
)

_GENERIC_WORDS = frozenset({
    "açık", "hava", "outdoor", "kış", "yaz", "bahar", "sonbahar",
    "gece", "festival", "special", "özel", "istanbul", "ankara",
    "izmir", "türkiye", "anatolian", "yıllık", "geleneksel",
    "uluslararası", "international", "ulusal", "national",
    "anı", "anısına", "şeref", "onur", "büyük", "grand",
})


def _ascii_fold(text: str) -> str:
    """Lowercase + strip combining characters (handles Turkish İ/Ş/Ğ → ASCII).

    Python's str.lower() turns 'İ' (U+0130) into 'i̇' (two codepoints),
    which never matches the plain 'i' in ASCII strings. NFKD decomposition
    followed by stripping combining marks resolves this consistently.
    """
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _is_plausible_performer(name: str) -> bool:
    """Return True if name looks like a real artist/performer name."""
    if not name or len(name) < 3 or len(name) > 60:
        return False
    if _YEAR_OR_ANNIVERSARY_RE.search(name):
        return False
    folded_words = set(_ascii_fold(name).split())
    return not folded_words.intersection(_GENERIC_WORDS)


def extract_performer_from_title(title: str, event_type: str) -> Optional[str]:
    """Try to extract a performer/artist name from the event title.

    Works for all event types. Returns None when the performer cannot be
    identified with reasonable confidence.
    """
    if not title:
        return None

    cleaned = title.strip()
    cleaned = _PAREN_SUFFIX_RE.sub("", cleaned).strip()
    lower = cleaned.lower()

    # "Artist - Subtitle" pattern — take everything before the first " - "
    if " - " in cleaned:
        before_dash = cleaned.split(" - ", 1)[0].strip()
        if _is_plausible_performer(before_dash):
            return before_dash

    # Try stripping known suffixes — first match wins
    for suffix in _ALL_SUFFIXES:
        if lower.endswith(suffix):
            candidate = cleaned[: -len(suffix)].strip().rstrip(",-–|")
            if _is_plausible_performer(candidate):
                return candidate
            return None  # suffix matched but result is not plausible — stop here

    return None
