"""Entry point for SerpAPI events sync pipeline."""

from __future__ import annotations

import json
import logging
import os
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
from providers.serpapi_events import SerpApiEventsProvider
from services.sync_service import SyncService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
_logger = logging.getLogger(__name__)


def _save_results(events: List[NormalizedEvent], request_count: int) -> None:
    out_dir = _ROOT / "data" / "serpapi"
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
        "requests_used": request_count,
    }
    stats_path.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _logger.info("Saved %s events to %s", len(events), out_dir)


def main() -> int:
    _logger.info("=== SerpAPI sync started ===")

    provider = SerpApiEventsProvider()

    if not provider._client.is_enabled:
        _logger.warning("SerpAPI disabled (no API key) — exiting")
        return 0

    city = settings.serpapi_city.strip() or "Istanbul"

    try:
        events = provider.fetch_events(city)
        _logger.info("SerpAPI: %s events fetched", len(events))
    except Exception as exc:
        _logger.error("SerpApiEventsProvider failed: %s", exc)
        return 1

    _save_results(events, provider.request_count)

    if settings.sync_mode == "dry_run":
        _logger.info("sync_mode=dry_run — skipping backend sync")
        return 0

    if not events:
        _logger.info("No events — skipping backend sync")
        return 0

    sync_run_id = f"serpapi-{uuid.uuid4().hex[:8]}-{datetime.now().strftime('%H%M%S')}"
    _logger.info("Starting backend sync sync_run_id=%s", sync_run_id)

    try:
        sync_service = SyncService()
        success = sync_service.sync_events_to_backend_bulk(events, sync_run_id)
        if success:
            _logger.info("Backend sync completed successfully")
        else:
            _logger.error("Backend sync reported failure")
        sync_service.trigger_stale_cleanup(sync_run_id)
    except Exception as exc:
        _logger.error("Backend sync raised an exception: %s", exc)
        return 1

    _logger.info("=== SerpAPI sync finished ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
