"""Entry point for Ticketmaster sync pipeline."""

from __future__ import annotations

import json
import logging
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
from services.sync_service import SyncService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
_logger = logging.getLogger(__name__)


def _save_results(events: List[NormalizedEvent]) -> None:
    out_dir = _ROOT / "data" / "ticketmaster"
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
    }
    stats_path.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _logger.info("Saved %s events to %s", len(events), out_dir)


def main() -> int:
    _logger.info("=== Ticketmaster sync started ===")

    try:
        events = TicketmasterProvider().fetch_and_parse()
        _logger.info("Ticketmaster: %s events", len(events))
    except Exception as exc:
        _logger.error("TicketmasterProvider failed: %s", exc)
        events = []

    _save_results(events)

    if settings.sync_mode == "dry_run":
        _logger.info("sync_mode=dry_run — skipping backend sync")
        return 0

    if not events:
        _logger.warning("No events fetched, skipping backend sync")
        return 0

    sync_service = SyncService()
    sync_run_id = f"ticketmaster-{uuid.uuid4().hex[:8]}-{datetime.now().strftime('%H%M%S')}"
    _logger.info("Starting backend sync provider=Ticketmaster events=%s sync_run_id=%s", len(events), sync_run_id)

    overall_success = True
    try:
        success = sync_service.sync_events_to_backend_bulk(events, sync_run_id)
        if success:
            _logger.info("Backend sync completed successfully provider=Ticketmaster")
        else:
            _logger.error("Backend sync reported failure provider=Ticketmaster")
            overall_success = False
    except Exception as exc:
        _logger.error("Backend sync raised an exception provider=Ticketmaster: %s", exc)
        overall_success = False

    cleanup_run_id = f"ticketmaster-cleanup-{datetime.now().strftime('%H%M%S')}"
    try:
        sync_service.trigger_stale_cleanup(cleanup_run_id, provider="Ticketmaster")
    except Exception as exc:
        _logger.error("Stale cleanup failed provider=Ticketmaster: %s", exc)

    _logger.info("=== Ticketmaster sync finished ===")
    return 0 if overall_success else 1


if __name__ == "__main__":
    sys.exit(main())
