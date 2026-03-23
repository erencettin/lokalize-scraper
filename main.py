import logging
from providers.kultur_istanbul import KulturIstanbulProvider
from providers.etkinlik_io import EtkinlikIoProvider
from providers.mobilet import MobiletProvider
from services.sync_service import SyncService
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
        # Add more here as implemented
    ]
    
    # 3. Execute
    total_events = 0
    for provider in providers:
        logging.info(f"Running provider: {provider.name}")
        try:
            events = provider.fetch_and_parse()
            logging.info(f"Fetched {len(events)} events from {provider.name}")
            
            for event in events:
                sync_service.sync_event(event)
                total_events += 1
                
        except Exception as e:
            logging.error(f"Provider {provider.name} failed: {e}")

    logging.info(f"Scrape completed. Total events processed: {total_events}")

if __name__ == "__main__":
    main()
