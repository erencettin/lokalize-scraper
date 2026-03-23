import logging
from providers.etkinlik_io import EtkinlikIoProvider
from services.sync_service import SyncService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test():
    provider = EtkinlikIoProvider()
    events = provider.fetch_and_parse()
    # just pick one event that we know is a duplicate
    sync_service = SyncService()
    if events:
        logging.info("Testing sync on an existing item to trigger duplicate handling...")
        sync_service.sync_event(events[0])
        print("Done!")

if __name__ == "__main__":
    test()
