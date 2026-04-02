"""Compliance utilities for respectful web scraping.

All scrapers MUST use these utilities to ensure:
- robots.txt compliance (RobotsChecker)
- Rate limiting (RateLimiter)
- Transparent user-agent identification (get_scraper_user_agent)
"""

from utils.compliance.robots_checker import RobotsChecker
from utils.compliance.rate_limiter import RateLimiter
from utils.compliance.user_agent import get_scraper_user_agent

__all__ = ["RobotsChecker", "RateLimiter", "get_scraper_user_agent"]
