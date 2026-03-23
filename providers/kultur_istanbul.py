import requests
from bs4 import BeautifulSoup
from typing import List, Optional
from datetime import datetime
import pytz
import logging
import json
import re

from providers.base_provider import BaseProvider
from models.normalized_event import NormalizedEvent, NormalizedOccurrence, NormalizedSource, PriceInfo
from utils.date_parser import DateParser

class KulturIstanbulProvider(BaseProvider):
    def __init__(self):
        super().__init__("KulturIstanbul", mode="http")
        self.base_api_url = "https://kultur.istanbul/wp-json/wp/v2/event_listing?per_page=50"
        self.logger = logging.getLogger(__name__)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
        }

    def fetch_and_parse(self) -> List[NormalizedEvent]:
        self.logger.info(f"Fetching events from {self.base_api_url}")
        
        try:
            import urllib3
            urllib3.disable_warnings()
            # We must use verify=False because sometimes their SSL cert is weird, but requests works fine usually.
            response = requests.get(self.base_api_url, headers=self.headers, verify=False, timeout=20)
            response.raise_for_status()
            events_json = response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch event listing JSON: {e}")
            return []
            
        self.logger.info(f"Found {len(events_json)} event items from REST API")

        normalized_events = []
        for i, item in enumerate(events_json, 1):
            try:
                title = item.get("title", {}).get("rendered", "").strip()
                self.logger.info(f"[{i}/{len(events_json)}] Fetching details for: {title}")
                event = self._parse_api_item(item)
                if event:
                    self.logger.info(f"  -> Successfully parsed: {event.title} at {event.occurrences[0].venue_name}")
                    normalized_events.append(event)
            except Exception as e:
                self.logger.error(f"Error parsing event {item.get('id')}: {e}")

        return normalized_events

    def _parse_api_item(self, item: dict) -> Optional[NormalizedEvent]:
        # Basic fields from JSON
        event_id = str(item.get("id"))
        import html
        title = item.get("title", {}).get("rendered", "").strip()
        title = html.unescape(title)
        link = item.get("link", "")
        
        if not title or not link:
            return None

        # Description
        description = item.get("content", {}).get("rendered", "")
        # Strip HTML from description
        desc_soup = BeautifulSoup(description, 'html.parser')
        description_text = desc_soup.get_text(separator=' \n ', strip=True)

        # Image
        image_url = None
        try:
            og_images = item.get("yoast_head_json", {}).get("og_image", [])
            if og_images:
                image_url = og_images[0].get("url")
        except:
            pass

        # Since WP REST API doesn't expose event dates natively, we MUST fetch the detail page
        try:
            res = requests.get(link, headers=self.headers, verify=False, timeout=15)
            res.raise_for_status()
            detail_soup = BeautifulSoup(res.text, 'html.parser')
        except Exception as e:
            self.logger.warning(f"Could not fetch detail page for {title} - {link}: {e}")
            return None

        # Extract Date & Time
        date_text_els = detail_soup.select(".wpem-event-date-time span, .wpem-event-date-time, .wpem-event-date-text")
        time_text_els = detail_soup.select(".wpem-event-time-text")
        
        # WP Event Manager usually outputs: 20-03-2026 (date) and 13:00 (time)
        date_str = ""
        time_str = "00:00"
        
        if date_text_els:
            raw_date = date_text_els[0].text.strip()
            # Some events are ranges like "20-02-2026 \n - \n 14-03-2026". We extract the *first* date.
            date_match = re.search(r'\d{2}[-\./]\d{2}[-\./]\d{4}', raw_date)
            if date_match:
                date_str = date_match.group(0)
            else:
                date_str = raw_date.split('\n')[0].split(' - ')[0].strip()
            
        if time_text_els:
            time_str = time_text_els[0].text.strip()
            # sometimes time has " - " if it's a range, just take the first part
            time_str = time_str.split("-")[0].strip()
            time_str = time_str.split(" ")[0].strip()

        if not date_str:
            return None

        # Date parsing
        # format is usually DD-MM-YYYY or YYYY-MM-DD
        start_at_utc = None
        try:
            # Handle standard dot mapping as well just in case
            date_str = date_str.replace(".", "-").replace("/", "-")
            parts = date_str.split("-")
            
            # Detect if it's YYYY-MM-DD or DD-MM-YYYY
            if len(parts[0]) == 4:
                naive_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            else:
                naive_dt = datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M")
                
            local_tz = pytz.timezone("Europe/Istanbul")
            local_dt = local_tz.localize(naive_dt)
            start_at_utc = local_dt.astimezone(pytz.UTC)
        except Exception as e:
            self.logger.debug(f"Failed to parse date '{date_str} {time_str}' from raw '{raw_date if date_text_els else ''}': {e}")
            return None

        # Venue
        venue_name = "İstanbul"
        venue_els = detail_soup.select(".wpem-event-location span, .wpem-single-event-location")
        if venue_els:
            venue_name = venue_els[0].text.strip()

        # Price Info
        categories = [c.text.strip().lower() for c in detail_soup.select('.wpem-event-type-text')]
        price_text = "Belirtilmemiş"
        
        # Heuristics based on previously extracted tags
        if "ücretsiz" in categories:
             price_text = "Ücretsiz"
        else:
             # Look for TL amounts if not ucretsiz
             for text in categories:
                 if "tl" in text or "₺" in text:
                     price_text = text
                     break
        
        if price_text == "Belirtilmemiş":
            # Check full description text for price as fallback
             desc_lower = description_text.lower()
             if "ücretsiz" in desc_lower and "ücretsizdir" in desc_lower:
                  price_text = "Ücretsiz"

        event_type = self._map_category(categories)

        # Build Normalized Data
        source = NormalizedSource(
            provider=self.name,
            external_id=event_id,
            title=title,
            source_url=link,
            price=PriceInfo(text=price_text)
        )

        local_date, local_time, tz = DateParser.to_local_parts(start_at_utc)

        occurrence = NormalizedOccurrence(
            start_at_utc=start_at_utc,
            local_date=local_date,
            local_time=local_time,
            timezone=tz,
            venue_name=venue_name,
            sources=[source]
        )

        return NormalizedEvent(
            title=title,
            description=description_text[:2000], 
            type=event_type,
            city_name="İstanbul",
            image_url=image_url,
            occurrences=[occurrence]
        )

    def _map_category(self, categories: List[str]) -> str:
        # Default fallback
        event_type = "experience"
        
        for cat in categories:
            if "konser" in cat or "müzik" in cat:
                event_type = "concert"
                break
            elif "tiyatro" in cat or "oyun" in cat or "stand" in cat or "standup" in cat:
                event_type = "theatre"
                break
            elif "sergi" in cat:
                event_type = "experience"
                break
            elif "festival" in cat:
                event_type = "festival"
                break
            elif "film" in cat or "sinema" in cat:
                event_type = "show"
                break
            elif "atölye" in cat or "workshop" in cat:
                event_type = "experience"
                break
                
        return event_type
