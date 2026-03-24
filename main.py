import logging
from providers.kultur_istanbul import KulturIstanbulProvider
from providers.etkinlik_io import EtkinlikIoProvider
from providers.mobilet import MobiletProvider
from providers.biletix import BiletixProvider
from services.sync_service import SyncService
from datetime import datetime
import pytz
from config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    logging.info(f"Starting Lokalize Scraper in {settings.sync_mode} mode")
    
    # 1. Initialize core services
    sync_service = SyncService()
    
    # 2. Register providers
    providers = [
        KulturIstanbulProvider(),
        EtkinlikIoProvider(),
        MobiletProvider(),
        BiletixProvider(),
        # Add more here as implemented
    ]
    
    # 3. Execute
    total_stats = {"found": 0, "inserted": 0, "updated": 0, "failed": 0, "deactivated": 0}
    synced_cities = set()
    run_start_time = datetime.now(pytz.UTC)

    for provider in providers:
        logging.info(f"Running provider: {provider.name}")
        
        # Create Run Log
        run_res = sync_service._supabase.create_run(provider.name, run_start_time.isoformat())
        run_id = run_res.data[0]["id"] if run_res.data else None
        
        provider_stats = {"found": 0, "inserted": 0, "updated": 0, "failed": 0, "deactivated": 0}
        
        try:
            events = provider.fetch_and_parse()
            provider_stats["found"] = len(events)
            logging.info(f"Fetched {len(events)} events from {provider.name}")
            
            provider_synced_cities = set()
            for event in events:
                event_stats = sync_service.sync_event(event)
                provider_stats["inserted"] += event_stats["inserted"]
                provider_stats["updated"] += event_stats["updated"]
                provider_stats["failed"] += event_stats["failed"]
                
                synced_cities.add(event.city_name)
                provider_synced_cities.add(event.city_name)
            
            # Cleanup stale sources for THIS provider
            for city in provider_synced_cities:
                deactivated = sync_service.deactivate_stale_sources(city, provider.name, run_start_time)
                provider_stats["deactivated"] += deactivated
            
            # Finish Run Log (Success)
            if run_id:
                sync_service._supabase.finish_run(run_id, provider_stats, status="success")
                
        except Exception as e:
            logging.error(f"Provider {provider.name} failed: {e}")
            if run_id:
                sync_service._supabase.finish_run(run_id, provider_stats, status="failed", error_msg=str(e))
        
        # Add to absolute totals
        for k in total_stats: total_stats[k] += provider_stats[k]

    # 4. Final Cleanup/Archive (Past dates & Orphaned items, scoped by city)
    logging.info("Starting final lifecycle cleanup...")
    for city in synced_cities:
        sync_service.deactivate_expired_events(city)
        orphaned = sync_service.cleanup_orphaned_items(city)
        total_stats["deactivated"] += orphaned

    logging.info(f"Scrape completed. Stats: {total_stats}")

if __name__ == "__main__":
    main()
