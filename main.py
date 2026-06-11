import logging
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor
from providers.ticketmaster import TicketmasterProvider
from providers.municipal_rss import MunicipalRssProvider
from providers.municipal_web import MunicipalWebProvider
from providers.biletimgo import BiletimgoProvider
from providers.biletcom import BiletcomProvider
from providers.biletinial import BiletinialProvider

from services.sync_service import SyncService
from services.events_sync_service import EventsSyncService
from datetime import datetime
import pytz
import uuid
from config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

_MAX_PARALLEL_WORKERS = 5

def run_provider(provider, sync_service, sync_run_id, total_stats, total_stats_lock):
    """Executes the fetch and bulk-sync logic for a single provider."""
    logging.info("Running provider: %s", provider.name)

    provider_stats = {"found": 0, "synced": 0, "failed": 0}

    try:
        events = provider.fetch_and_parse()
        provider_stats["found"] = len(events)
        logging.info("Fetched %d events from %s", len(events), provider.name)

        if events:
            success = sync_service.sync_events_to_backend_bulk(events, sync_run_id)
            if success:
                provider_stats["synced"] = len(events)
            else:
                provider_stats["failed"] = len(events)

    except Exception as e:
        logging.error(
            "Provider %s failed with %s. Sensitive details are redacted.",
            provider.name,
            type(e).__name__,
        )
        provider_stats["failed"] = provider_stats.get("found", 0) or 1

    # Thread-safe merge into shared totals
    with total_stats_lock:
        for k in provider_stats:
            if k in total_stats:
                total_stats[k] += provider_stats[k]

def main():
    parser = argparse.ArgumentParser(description="Lokalize Scraper V4 Orchestrator")
    parser.add_argument("--provider", type=str, help="Run only a specific provider")
    parser.add_argument("--parallel", action="store_true", help="Run providers in parallel")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and normalize data without persisting")
    
    args = parser.parse_args()
    dry_run = args.dry_run or settings.sync_mode.lower() == "dry_run"

    # 1. Register providers
    all_providers = [
        TicketmasterProvider(),
        MunicipalRssProvider(),
        MunicipalWebProvider(),
        BiletimgoProvider(),
        BiletcomProvider(),
        BiletinialProvider(),
    ]

    # Filter providers if requested
    providers_to_run = all_providers
    if args.provider:
        providers_to_run = [p for p in all_providers if p.name.lower() == args.provider.lower()]
        if not providers_to_run:
            logging.error("Provider not found or disabled: %s", args.provider)
            return

    logging.info(f"Starting Lokalize V4 Sync (Mode: {'dry_run' if dry_run else settings.sync_mode})")
    
    # 2. Initialize sync service
    sync_service = SyncService()
    sync_run_id = f"v4-{uuid.uuid4().hex[:8]}-{datetime.now().strftime('%H%M%S')}"
    
    # 3. Execute
    total_stats = {"found": 0, "synced": 0, "failed": 0}
    total_stats_lock = threading.Lock()

    if args.parallel:
        logging.info("Running in parallel mode...")
        with ThreadPoolExecutor(max_workers=_MAX_PARALLEL_WORKERS) as executor:
            for provider in providers_to_run:
                executor.submit(run_provider, provider, sync_service, sync_run_id, total_stats, total_stats_lock)
    else:
        for provider in providers_to_run:
            run_provider(provider, sync_service, sync_run_id, total_stats, total_stats_lock)

    # 4. Final Cleanup (Deactivate stale records NOT seen in this sync run)
    if providers_to_run:
        logging.info(f"Sync complete for RunId: {sync_run_id}. Triggering stale cleanup...")
        sync_service.trigger_stale_cleanup(sync_run_id)

    # 5. Nearby Events (SerpAPI)
    nearby_events_service = EventsSyncService()
    nearby_events_stats = nearby_events_service.run(dry_run=dry_run, city=settings.serpapi_city)

    logging.info(
        "SerpAPI Events sync summary: (fetched=%s saved=%s deactivated=%s failed=%s requests=%s)",
        nearby_events_stats.fetched,
        nearby_events_stats.saved,
        nearby_events_stats.deactivated,
        nearby_events_stats.failed,
        nearby_events_stats.request_count,
    )

    logging.info("Daily SerpAPI usage: total_requests=%s", nearby_events_stats.request_count)
    logging.info(f"V4 Aggregator Sync completed. Stats: {total_stats}")

if __name__ == "__main__":
    main()
