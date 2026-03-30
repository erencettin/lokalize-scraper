"""Smoke test for municipal web provider runtime behavior."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import List

from config import settings
from providers.municipal_web import MunicipalWebProvider
from providers.municipal_web.models import MunicipalSite


def _apply_fast_mode() -> None:
    settings.municipal_web_timeout_seconds = 5
    settings.municipal_web_max_retries = 1
    settings.municipal_web_list_delay_seconds = 0.0
    settings.municipal_web_detail_delay_seconds = 0.0
    settings.municipal_web_max_items_per_site = 5


def _filtered_sites(provider: MunicipalWebProvider, max_sites: int) -> List[MunicipalSite]:
    sites = provider._registry.get_sites()  # pylint: disable=protected-access
    return sites[:max_sites] if max_sites > 0 else sites


def main() -> None:
    parser = argparse.ArgumentParser(description="Municipal web smoke test")
    parser.add_argument("--fast", action="store_true", help="Use low-timeout, single-retry settings")
    parser.add_argument("--max-sites", type=int, default=0, help="Limit number of sites to test (0 = all)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    settings.municipal_web_enabled = True
    if args.fast:
        _apply_fast_mode()

    provider = MunicipalWebProvider()
    if args.max_sites > 0:
        selected_sites = _filtered_sites(provider, args.max_sites)
        provider._registry.get_sites = lambda: selected_sites  # pylint: disable=protected-access
        print(f"Using {len(selected_sites)} site(s)")

    events = provider.fetch_and_parse()
    print(f"Total events: {len(events)}")
    for event in events[:3]:
        occurrence = event.occurrences[0]
        print(f"  {event.title} | {occurrence.local_date}")


if __name__ == "__main__":
    main()
