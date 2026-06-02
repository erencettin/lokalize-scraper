"""Entry point for Bilet.com Affiliate API sync pipeline."""

from __future__ import annotations

import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import settings
from models.normalized_event import NormalizedEvent
from providers.biletcom.provider import BiletcomProvider
from services.sync_service import SyncService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
_logger = logging.getLogger(__name__)


def _save_results(events: List[NormalizedEvent]) -> None:
    out_dir = _ROOT / "data" / "biletcom"
    out_dir.mkdir(parents=True, exist_ok=True)

    events_path = out_dir / "events.json"
    stats_path = out_dir / "stats.json"

    events_path.write_text(
        json.dumps(
            [e.model_dump(mode="json") for e in events],
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    stats_path.write_text(
        json.dumps(
            {"last_fetch": datetime.now(timezone.utc).isoformat(), "total_events": len(events)},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _logger.info("Saved %s events to %s", len(events), out_dir)


def main() -> int:
    _logger.info("=== bilet.com sync started ===")

    events: List[NormalizedEvent] = []
    try:
        events = BiletcomProvider().fetch_and_parse()
        _logger.info("bilet.com: %s events", len(events))
    except Exception as exc:
        _logger.error("BiletcomProvider failed: %s", exc)
        return 1

    _save_results(events)

    if settings.sync_mode == "dry_run":
        _logger.info("sync_mode=dry_run — skipping backend sync")
        return 0

    if not events:
        _logger.warning("No events fetched, skipping backend sync")
        return 0

    sync_service = SyncService()
    sync_run_id = f"biletcom-{uuid.uuid4().hex[:8]}-{datetime.now().strftime('%H%M%S')}"
    _logger.info("Starting backend sync events=%s sync_run_id=%s", len(events), sync_run_id)

    try:
        success = sync_service.sync_events_to_backend_bulk(events, sync_run_id)
        if success:
            _logger.info("Backend sync completed successfully")
        else:
            _logger.error("Backend sync reported failure")
            return 1
    except Exception as exc:
        _logger.error("Backend sync raised an exception: %s", exc)
        return 1

    try:
        sync_service.trigger_stale_cleanup(sync_run_id, provider="bilet.com")
    except Exception as exc:
        _logger.error("Stale cleanup failed: %s", exc)

    _logger.info("=== bilet.com sync finished ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
