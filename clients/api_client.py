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
            logger.info("Sync Success: %s", response.json())
            return True
        except requests.exceptions.RequestException as exc:
            logger.error("Sync Failed: %s", exc)
            if hasattr(exc, "response") and exc.response is not None:
                logger.error("Response Body: %s", exc.response.text)
                with open("error_dump.txt", "w", encoding="utf-8") as f:
                    f.write(exc.response.text)
            return False
