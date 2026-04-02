"""Tests for utils/compliance/* modules."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# RobotsChecker
# ---------------------------------------------------------------------------

class TestRobotsChecker:
    def _make_checker(self):
        from utils.compliance.robots_checker import RobotsChecker
        return RobotsChecker(ttl_seconds=60)

    def test_disallowed_path_returns_false(self):
        """Paths explicitly disallowed in robots.txt must return False."""
        from utils.compliance.robots_checker import RobotsChecker, _cache
        _cache.clear()

        mock_parser = MagicMock()
        mock_parser.can_fetch.return_value = False

        checker = RobotsChecker()
        with patch.object(checker, "_get_parser", return_value=mock_parser):
            result = checker.is_allowed(
                "https://example.com/admin/", user_agent="IstanbulEtkinlikBot/1.0"
            )
        assert result is False

    def test_allowed_path_returns_true(self):
        from utils.compliance.robots_checker import RobotsChecker
        mock_parser = MagicMock()
        mock_parser.can_fetch.return_value = True

        checker = RobotsChecker()
        with patch.object(checker, "_get_parser", return_value=mock_parser):
            result = checker.is_allowed("https://example.com/etkinlik/")
        assert result is True

    def test_fetch_failure_defaults_to_allow(self):
        """Network errors must NOT block scraping — default to True."""
        from utils.compliance.robots_checker import RobotsChecker
        checker = RobotsChecker()
        with patch.object(checker, "_get_parser", side_effect=Exception("timeout")):
            result = checker.is_allowed("https://example.com/")
        assert result is True

    def test_crawl_delay_returns_float(self):
        from utils.compliance.robots_checker import RobotsChecker
        mock_parser = MagicMock()
        mock_parser.crawl_delay.return_value = 2.5

        checker = RobotsChecker()
        with patch.object(checker, "_get_parser", return_value=mock_parser):
            delay = checker.crawl_delay("https://example.com/")
        assert delay == 2.5

    def test_crawl_delay_none_when_not_set(self):
        from utils.compliance.robots_checker import RobotsChecker
        mock_parser = MagicMock()
        mock_parser.crawl_delay.return_value = None

        checker = RobotsChecker()
        with patch.object(checker, "_get_parser", return_value=mock_parser):
            delay = checker.crawl_delay("https://example.com/")
        assert delay is None

    def test_domain_extraction(self):
        from utils.compliance.robots_checker import RobotsChecker
        checker = RobotsChecker()
        assert checker._extract_domain("https://www.bakirkoy.bel.tr/etkinlik/123") == "https://www.bakirkoy.bel.tr"
        assert checker._extract_domain("http://api.ticketmaster.com/v2/events") == "http://api.ticketmaster.com"


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def test_domain_extracted_from_url(self):
        from utils.compliance.rate_limiter import RateLimiter
        limiter = RateLimiter()
        assert limiter._extract_domain("https://api.ticketmaster.com/v2/events") == "api.ticketmaster.com"
        assert limiter._extract_domain("https://www.bakirkoy.bel.tr/etkinlik") == "www.bakirkoy.bel.tr"

    def test_ticketmaster_uses_5s_delay(self):
        from utils.compliance.rate_limiter import RateLimiter
        limiter = RateLimiter()
        delay = limiter._get_delay("api.ticketmaster.com")
        assert delay == 5.0

    def test_serpapi_uses_2s_delay(self):
        from utils.compliance.rate_limiter import RateLimiter
        limiter = RateLimiter()
        delay = limiter._get_delay("serpapi.com")
        assert delay == 2.0

    def test_unknown_domain_uses_default(self):
        from utils.compliance.rate_limiter import RateLimiter, RATE_LIMITS
        limiter = RateLimiter()
        delay = limiter._get_delay("www.someunknownsite.com")
        assert delay == RATE_LIMITS["default"]

    def test_subdomain_of_serpapi_uses_configured_delay(self):
        """sub.serpapi.com should match serpapi.com via partial match."""
        from utils.compliance.rate_limiter import RateLimiter
        limiter = RateLimiter()
        delay = limiter._get_delay("api.serpapi.com")
        assert delay == 2.0

    def test_wait_for_domain_sleeps_for_new_domain(self):
        """First call to a new domain should sleep for ~delay seconds."""
        from utils.compliance.rate_limiter import RateLimiter, RATE_LIMITS
        limiter = RateLimiter()
        # Pre-set last_request to slightly less than delay ago
        domain = "fresh.example.com"
        default_delay = RATE_LIMITS["default"]
        limiter._last_request[domain] = time.monotonic() - (default_delay - 0.5)

        start = time.monotonic()
        with patch("utils.compliance.rate_limiter.time.sleep") as mock_sleep:
            limiter.wait_for_domain(f"https://{domain}/page")
        # Sleep should have been called with ~0.5s
        if mock_sleep.called:
            called_with = mock_sleep.call_args[0][0]
            assert 0.0 < called_with <= default_delay

    def test_wait_for_domain_no_sleep_when_enough_time_elapsed(self):
        """If enough time has passed, wait_for_domain should NOT sleep."""
        from utils.compliance.rate_limiter import RateLimiter, RATE_LIMITS
        limiter = RateLimiter()
        domain = "old.example.com"
        # Make it look like last request was a long time ago
        limiter._last_request[domain] = time.monotonic() - 999
        with patch("utils.compliance.rate_limiter.time.sleep") as mock_sleep:
            limiter.wait_for_domain(f"https://{domain}/page")
        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# User Agent
# ---------------------------------------------------------------------------

class TestUserAgent:
    def test_canonical_user_agent_contains_bot_identifier(self):
        from utils.compliance.user_agent import get_scraper_user_agent
        ua = get_scraper_user_agent()
        assert "IstanbulEtkinlikBot" in ua

    def test_canonical_user_agent_contains_version(self):
        from utils.compliance.user_agent import get_scraper_user_agent
        ua = get_scraper_user_agent()
        assert "1.0" in ua

    def test_canonical_user_agent_does_not_impersonate_browser(self):
        from utils.compliance.user_agent import get_scraper_user_agent
        ua = get_scraper_user_agent()
        assert "Mozilla" not in ua
        assert "Chrome" not in ua
        assert "Safari" not in ua

    def test_canonical_user_agent_contains_contact_url(self):
        from utils.compliance.user_agent import get_scraper_user_agent
        ua = get_scraper_user_agent()
        assert "lokalizeapp.com" in ua

    def test_get_scraper_user_agent_returns_string(self):
        from utils.compliance.user_agent import get_scraper_user_agent
        assert isinstance(get_scraper_user_agent(), str)
