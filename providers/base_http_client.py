import abc
import requests
from typing import Optional, Any

class BaseHttpClient(abc.ABC):
    """Abstract base class for all scraper HTTP clients."""

    @abc.abstractmethod
    def setup_session(self) -> None:
        """Initialize requests session."""
        pass

    @abc.abstractmethod
    def close_session(self) -> None:
        """Close active session and clean up resources."""
        pass
