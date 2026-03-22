import requests
from bs4 import BeautifulSoup
import re
from typing import List
from providers.base_provider import BaseProvider
from models.normalized_event import NormalizedEvent, NormalizedOccurrence, NormalizedSource, PriceInfo
from utils.date_parser import DateParser
import logging

class KulturIstanbulProvider(BaseProvider):
    def __init__(self):
        super().__init__("KulturIstanbul", mode="http")
        self.base_url = "https://kultur.istanbul"
        self.events_url = f"{self.base_url}/etkinlikler/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def fetch_and_parse(self) -> List[NormalizedEvent]:
        logging.info(f"Fetching events from {self.events_url}")
        
        response = requests.get(self.events_url, headers=self.headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        event_cards = soup.select(".wpem-event-layout-column")
        
        normalized_events = []
        logging.info(f"Found {len(event_cards)} event cards")

        for card in event_cards:
            try:
                event = self._parse_card(card)
                if event:
                    normalized_events.append(event)
            except Exception as e:
                logging.error(f"Error parsing card in {self.name}: {e}")
                
        return normalized_events

    def _parse_card(self, card) -> Optional[NormalizedEvent]:
        title_el = card.select_one(".wpem-event-infomation h3")
        if not title_el:
            return None
        
        title = title_el.get_text(strip=True)
        
        # Link
        link_el = card.select_one("a.wpem-event-action-url")
        link = link_el['href'] if link_el else self.base_url
        
        # Date
        date_el = card.select_one(".wpem-event-date span")
        date_str = date_el.get_text(strip=True) if date_el else ""
        
        # Venue
        venue_el = card.select_one(".wpem-event-location span")
        venue = venue_el.get_text(strip=True) if venue_el else "İstanbul"
        
        # Image
        image_url = None
        banner_el = card.select_one(".wpem-event-banner-img")
        if banner_el and 'style' in banner_el.attrs:
            style = banner_el['style']
            match = re.search(r'url\([\'"]?(.*?)[\'"]?\)', style)
            if match:
                image_url = match.group(1)

        # Categories
        cat_elements = card.select(".wpem-event-category span")
        categories = [c.get_text(strip=True) for c in cat_elements]
        main_category = categories[0] if categories else "Diğer"
        
        # Parse Date/Time
        # Format: 13-03-2026 20:00 (or simple date range)
        # We take the first part as start time
        start_at_utc = None
        if date_str:
            try:
                # Handle range if exists: "11-03-2026 20:00 - 28-03-2026"
                clean_date = date_str.split(" - ")[0].strip()
                start_at_utc = DateParser.parse_with_timezone(clean_date, "%d-%m-%Y %H:%M")
            except Exception as e:
                logging.warning(f"Could not parse date '{date_str}' for event '{title}': {e}")
                return None # Skip if date is invalid

        if not start_at_utc:
            return None

        # Create Normalized Objects
        source = NormalizedSource(
            provider=self.name,
            external_id=link.split('/')[-2] if '/' in link else None, # WP slug
            title=title,
            source_url=link,
            price=PriceInfo(text="Ücretsiz" if "Ücretsiz" in categories else "Belirtilmemiş") # Basic logic
        )
        
        occurrence = NormalizedOccurrence(
            start_at_utc=start_at_utc,
            venue_name=venue,
            district=None, # Extracting from venue if needed later
            sources=[source]
        )
        # Derive local parts
        DateParser.to_local_parts(occurrence.start_at_utc) # For side-effect or just use the utility in Sync
        
        # Logic to handle Multi-Date if one card had multiple dates (not common in this UI, 
        # usually 1 card = 1 occurrence in this plugin)
        
        return NormalizedEvent(
            title=title,
            type=main_category,
            city_name="Istanbul",
            image_url=image_url,
            occurrences=[occurrence]
        )
