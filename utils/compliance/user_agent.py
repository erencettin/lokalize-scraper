"""Transparent user-agent management for the scraper bot.

Rules
-----
- NEVER impersonate a browser (no "Mozilla/...", no "Chrome/..." strings).
- Always include a contact URL so site owners can reach us.
- CANONICAL_USER_AGENT is the single source of truth — import it everywhere.

Usage
-----
    from utils.compliance.user_agent import get_scraper_user_agent

    headers = {"User-Agent": get_scraper_user_agent()}
"""

from __future__ import annotations

# The one and only user-agent string for all scraping requests.
# Format: BotName/Version (contact-url; purpose)
CANONICAL_USER_AGENT: str = (
    "IstanbulEtkinlikBot/1.0 "
    "(+https://lokalizeapp.com/bot-info; etkinlik fiyat bilgisi toplama)"
)


def get_scraper_user_agent() -> str:
    """Return the canonical scraper user-agent string."""
    return CANONICAL_USER_AGENT
