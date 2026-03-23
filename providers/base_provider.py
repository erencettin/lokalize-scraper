from abc import ABC, abstractmethod
from typing import List
from models.normalized_event import NormalizedEvent

class BaseProvider(ABC):
    def __init__(self, name: str, mode: str = "http"):
        self.name = name
        self.mode = mode # http | browser

    @abstractmethod
    def fetch_and_parse(self) -> List[NormalizedEvent]:
        """
        Main entry point for a provider.
        Must return a list of NormalizedEvent objects.
        """
        return []
