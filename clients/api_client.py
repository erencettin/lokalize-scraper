import requests
import logging
from typing import List

logger = logging.getLogger(__name__)

class BackendApiClient:
    def __init__(self, base_url: str = "http://localhost:5170"):
        self.base_url = base_url.rstrip("/")

    def sync_events(self, payload: List[dict]):
        """
        Sends formatted IngestedEventDto objects to the .NET Backend Sync Endpoint.
        """
        url = f"{self.base_url}/api/events/sync"
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            logger.info(f"Sync Success: {response.json()}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Sync Failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response Body: {e.response.text}")
                with open("error_dump.txt", "w", encoding="utf-8") as f:
                    f.write(e.response.text)
            return False
