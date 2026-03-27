import requests
import logging
from typing import List, Dict

class BackendClient:
    def __init__(self, base_url: str = "http://localhost:5170"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def sync_events_bulk(self, events: List[Dict], sync_run_id: str) -> bool:
        """
        Sends events to the .NET V4 Aggregator API for bulk processing.
        """
        url = f"{self.base_url}/api/events/sync?syncRunId={sync_run_id}"
        try:
            logging.info(f"Sending {len(events)} events to backend for sync (RunId: {sync_run_id})...")
            response = self.session.post(url, json=events, timeout=60)
            
            if response.status_code == 200:
                logging.info(f"Successfully synced with backend: {response.json().get('message')}")
                return True
            else:
                logging.error(f"Backend sync failed ({response.status_code}): {response.text}")
                return False
        except Exception as e:
            logging.error(f"Error connecting to backend: {e}")
            return False

    def deactivate_stale(self, sync_run_id: str) -> bool:
        """
        Triggers the stale data cleanup lifecycle in the backend.
        """
        url = f"{self.base_url}/api/migration/deactivate-stale?syncRunId={sync_run_id}"
        try:
            response = self.session.post(url, timeout=30)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Error triggering stale cleanup: {e}")
            return False
