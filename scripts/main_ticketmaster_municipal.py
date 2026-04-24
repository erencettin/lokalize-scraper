"""Entry point for Ticketmaster + Municipal (RSS + Web) sync pipeline."""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

# Ensure repo root is on sys.path when invoked as `python scripts/...`
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import settings
from models.normalized_event import NormalizedEvent
from providers.ticketmaster.provider import TicketmasterProvider
from providers.municipal_rss.provider import MunicipalRssProvider
from providers.municipal_web.provider import MunicipalWebProvider
from services.sync_service import SyncService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
_logger = logging.getLogger(__name__)


def _save_results(events: List[NormalizedEvent], provider_counts: dict) -> None:
    out_dir = _ROOT / "data" / "ticketmaster_municipal"
    out_dir.mkdir(parents=True, exist_ok=True)

    events_path = out_dir / "events.json"
    stats_path = out_dir / "stats.json"

    events_payload = [e.model_dump(mode="json") for e in events]
    events_path.write_text(
        json.dumps(events_payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    stats = {
        "last_fetch": datetime.now(timezone.utc).isoformat(),
        "total_events": len(events),
        "provider_counts": provider_counts,
    }
    stats_path.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _logger.info("Saved %s events to %s", len(events), out_dir)


def main() -> int:
    _logger.info("=== Ticketmaster & Municipal sync started ===")

    tm_events: List[NormalizedEvent] = []
    rss_events: List[NormalizedEvent] = []
    web_events: List[NormalizedEvent] = []

    try:
        _logger.info("Running TicketmasterProvider...")
        tm_events = TicketmasterProvider().fetch_and_parse()
        _logger.info("Ticketmaster: %s events", len(tm_events))
    except Exception as exc:
        _logger.error("TicketmasterProvider failed: %s", exc)

    try:
        _logger.info("Running MunicipalRssProvider...")
        rss_events = MunicipalRssProvider().fetch_and_parse()
        _logger.info("MunicipalRSS: %s events", len(rss_events))
    except Exception as exc:
        _logger.error("MunicipalRssProvider failed: %s", exc)

    try:
        _logger.info("Running MunicipalWebProvider...")
        web_events = MunicipalWebProvider().fetch_and_parse()
        _logger.info("MunicipalWeb: %s events", len(web_events))
    except Exception as exc:
        _logger.error("MunicipalWebProvider failed: %s", exc)

    all_events = tm_events + rss_events + web_events
    provider_counts = {
        "Ticketmaster": len(tm_events),
        "MunicipalRSS": len(rss_events),
        "MunicipalWeb": len(web_events),
    }
    _logger.info("Total events: %s", len(all_events))

    _save_results(all_events, provider_counts)

    if settings.sync_mode == "dry_run":
        _logger.info("sync_mode=dry_run — skipping backend sync")
        return 0

    if not all_events:
        _logger.warning("No events fetched from any provider, skipping backend sync")
        return 0

    # CRITICAL: Each provider MUST be synced separately.
    # Merging all providers into a single bulk call causes dominantProvider detection
    # to pick the wrong provider, making GetChangedSinceAsync load the wrong events
    # and failing to find existing occurrences in the dedup cache — leading to duplicates.
    sync_service = SyncService()
    provider_batches = [
        ("Ticketmaster", tm_events),
        ("MunicipalRSS", rss_events),
        ("MunicipalWeb", web_events),
    ]

    overall_success = True
    last_sync_run_id = None
    for provider_name, events in provider_batches:
        if not events:
            _logger.info("Provider %s: no events, skipping", provider_name)
            continue
        sync_run_id = f"{provider_name.lower()}-{uuid.uuid4().hex[:8]}-{datetime.now().strftime('%H%M%S')}"
        last_sync_run_id = sync_run_id
        _logger.info("Starting backend sync provider=%s events=%s sync_run_id=%s", provider_name, len(events), sync_run_id)
        try:
            success = sync_service.sync_events_to_backend_bulk(events, sync_run_id)
            if success:
                _logger.info("Backend sync completed successfully provider=%s", provider_name)
            else:
                _logger.error("Backend sync reported failure provider=%s", provider_name)
                overall_success = False
        except Exception as exc:
            _logger.error("Backend sync raised an exception provider=%s: %s", provider_name, exc)
            overall_success = False

    # Trigger stale cleanup once after all providers are done.
    # Use the last sync_run_id as a marker (cleanup is idempotent).
    if last_sync_run_id:
        try:
            sync_service.trigger_stale_cleanup(last_sync_run_id)
        except Exception as exc:
            _logger.error("Stale cleanup failed: %s", exc)

    _logger.info("=== Ticketmaster & Municipal sync finished ===")
    return 0 if overall_success else 1


if __name__ == "__main__":
    sys.exit(main())
