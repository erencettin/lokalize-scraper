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

    sync_run_id = f"tm-muni-{uuid.uuid4().hex[:8]}-{datetime.now().strftime('%H%M%S')}"
    _logger.info("Starting backend sync sync_run_id=%s", sync_run_id)

    try:
        sync_service = SyncService()
        success = sync_service.sync_events_to_backend_bulk(all_events, sync_run_id)
        if success:
            _logger.info("Backend sync completed successfully")
        else:
            _logger.error("Backend sync reported failure")

        sync_service.trigger_stale_cleanup(sync_run_id)
    except Exception as exc:
        _logger.error("Backend sync raised an exception: %s", exc)
        return 1

    _logger.info("=== Ticketmaster & Municipal sync finished ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
