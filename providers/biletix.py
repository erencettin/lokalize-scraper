import requests
import logging
from typing import List, Optional
from datetime import datetime
import pytz
from providers.base_provider import BaseProvider
from models.normalized_event import NormalizedEvent, NormalizedOccurrence, NormalizedSource, PriceInfo

class BiletixProvider(BaseProvider):
    def __init__(self):
        super().__init__(name="Biletix", mode="http")
        self.base_url = "https://www.biletix.com"
        self.solr_url = "https://www.biletix.com/solr/tr/select/"
        self.api_url = "https://www.biletix.com/wbtxapi/api/v1/bxcached/event"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.biletix.com/",
            "channel": "INTERNET"
        }
        
        # Category Mapping
        self.category_map = {
            "KONSER": "concert",
            "TIYATRO": "theatre",
            "SPOR": "match",
            "SANAT": "experience",
            "AILE": "show",
            "EGITIM": "experience", # Map workshops to experience for now
            "SINEMA": "cinema",
            "FESTIVAL": "festival",
            "STAND-UP": "standup"
        }

    def fetch_and_parse(self) -> List[NormalizedEvent]:
        events = []
        try:
            # 1. Discovery via Solr (Istanbul only for now)
            params = {
                "start": 0,
                "rows": 500, 
                "fq": 'region:"ISTANBUL"',
                "q": "*:*",
                "wt": "json",
                "sort": "score desc,start asc"
            }
            
            # Add date range to filter out past events (optional but good)
            now_str = datetime.now(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            params["fq"] = [params["fq"], f"start:[{now_str} TO *]"]
            
            response = requests.get(self.solr_url, params=params, headers=self.headers, timeout=15)
            logging.info(f"Biletix Solr URL: {response.url}")
            response.raise_for_status()
            data = response.json()
            
            docs = data.get("response", {}).get("docs", [])
            if not docs:
                logging.warning(f"Biletix Solr response docs are empty. Response: {response.text[:200]}")
            logging.info(f"Biletix: Found {len(docs)} events in Solr discovery")
            
            for i, doc in enumerate(docs):
                if (i + 1) % 10 == 0:
                    logging.info(f"Biletix: Processing {i+1}/{len(docs)} events...")
                if not isinstance(doc, dict):
                    logging.warning(f"Biletix: Unexpected doc type {type(doc)}: {str(doc)[:100]}")
                    continue
                try:
                    event = self._parse_event(doc)
                    if event:
                        events.append(event)
                except Exception as e:
                    import traceback
                    logging.error(f"Error parsing Biletix doc {doc.get('id') if isinstance(doc, dict) else 'Unknown'}: {e}\n{traceback.format_exc()}")
                    
        except Exception as e:
            logging.error(f"Biletix fetch failed: {e}")
            
        return events

    def _parse_event(self, doc: dict) -> Optional[NormalizedEvent]:
        # Solr discovery fields: id, name, region, start, status, category_id
        event_code = doc.get("id") 
        if not event_code:
            logging.debug(f"Biletix: Solr doc missing 'id': {doc}")
            return None
            
        event_name = doc.get("name", "Biletix Event")
        logging.info(f"Biletix: Parsing event {event_code} - {event_name}")
            
        # 1. Fetch Event Detail (for description and images)
        detail_data = self._get_api_data(f"getEventDetail/{event_code}/INTERNET/tr")
        detail = {}
        if detail_data and isinstance(detail_data, dict):
            detail = detail_data.get("data") or {}
            
        # 2. Extract Basic Info
        title = detail.get("eventName", event_name)
        description = detail.get("eventDescription", "")
        
        # Category Logic
        raw_cat = doc.get("category_id", "OTHER")
        category = self.category_map.get(raw_cat, "experience")
        
        # Image Logic
        image_url = f"https://www.biletix.com/static/images/live/event/{event_code}.png"
        
        # 3. Fetch Performance List (for occurrences)
        perf_data = self._get_api_data(f"getPerformanceList/{event_code}/INTERNET/tr")
        if not perf_data:
            logging.debug(f"Biletix: Missing perf_list for {event_code}")
            return None
            
        perf_list = perf_data.get("data", []) if isinstance(perf_data, dict) else []
        if not perf_list:
            logging.debug(f"Biletix: Empty occurrences for {event_code}")
            return None
            
        occurrences = []
        for perf in perf_list:
            occ = self._parse_occurrence(perf, event_code, title)
            if occ:
                occurrences.append(occ)
        
        if not occurrences:
            logging.debug(f"Biletix: No valid occurrences for {event_code}")
            return None
            
        return NormalizedEvent(
            title=title,
            description=description,
            type=category,
            city_name="Istanbul",
            image_url=image_url if image_url else None,
            occurrences=occurrences
        )
    def _parse_occurrence(self, perf: dict, event_code: str, event_title: str) -> Optional[NormalizedOccurrence]:
        perf_code = perf.get("performanceCode")
        if not perf_code:
            return None
            
        # Date parsing
        # Biletix date format is ISO usually: 2026-03-23T21:00:00
        start_at_str = perf.get("performanceDate")
        # status = perf.get("status")
        # if status not in ["s01_onsale", "s02_comingsoon"]:
        #    return None
            
        start_at_utc = self._parse_date(start_at_str)
        if not start_at_utc:
            logging.warning(f"Failed to parse Biletix date {start_at_str} for event {event_code}")
            return None

        # Biletix dates are local (Europe/Istanbul)
        tz = pytz.timezone("Europe/Istanbul")
        local_dt = start_at_utc.astimezone(tz)
            
        venue_name = perf.get("venueName", "Biletix Venue")
        
        # Fetch Pricing for this performance
        # We need the internalPerformanceId (id in the perf list)
        internal_perf_id = perf.get("id")
        price_info = self._get_price_info(event_code, internal_perf_id) if internal_perf_id else PriceInfo(text="Fiyat bilgisi yok", min_value=None, max_value=None)
        
        # Resolve Ticket Status
        status = self._resolve_status(perf)
        
        source = NormalizedSource(
            provider="Biletix",
            external_id=f"{event_code}_{perf_code}",
            source_url=f"https://www.biletix.com/performance/{event_code}/{perf_code}/TURKIYE/tr",
            price=price_info,
            ticket_status=status,
            title=event_title # Biletix doesn't usually have performance-specific titles
        )
        
        return NormalizedOccurrence(
            venue_name=venue_name,
            start_at_utc=start_at_utc,
            local_date=local_dt.strftime("%Y-%m-%d"),
            local_time=local_dt.strftime("%H:%M"),
            sources=[source]
        )

    def _parse_date(self, date_val) -> datetime:
        if not date_val:
            return None
        try:
            if isinstance(date_val, (int, float)):
                # Milliseconds to seconds
                return datetime.fromtimestamp(date_val / 1000.0, pytz.UTC)
            if isinstance(date_val, str):
                if date_val.isdigit():
                    return datetime.fromtimestamp(int(date_val) / 1000.0, pytz.UTC)
                return datetime.fromisoformat(date_val.replace("Z", "+00:00"))
            return None
        except Exception:
            return None

    def _get_price_info(self, event_code: str, internal_perf_id: int) -> PriceInfo:
        # getPriceInfos/{eventCode}/{internalPerformanceId}/INTERNET/tr
        data = self._get_api_data(f"getPriceInfos/{event_code}/{internal_perf_id}/INTERNET/tr")
        if not data or not isinstance(data, list):
            return PriceInfo(text="Fiyat bilgisi yok", min_value=None, max_value=None)
            
        prices = []
        for p in data:
            if not isinstance(p, dict):
                continue
            # Biletix returns price as integer (cents)
            val_cents = p.get("price")
            if val_cents is not None:
                prices.append(float(val_cents) / 100.0)
                
        if not prices:
            return PriceInfo(text="Fiyat bilgisi yok", min_value=None, max_value=None)
            
        min_p = min(prices)
        max_p = max(prices)
        
        text = f"₺{min_p:.2f}" if min_p == max_p else f"₺{min_p:.2f} - ₺{max_p:.2f}"
        return PriceInfo(text=text, min_value=min_p, max_value=max_p, currency="TRY")

    def _resolve_status(self, perf: dict) -> str:
        # Biletix status flags: saleStatus, isSoldOut, etc.
        sale_status = perf.get("saleStatus")
        is_sold_out = perf.get("isSoldOut", False)
        
        if is_sold_out:
            return "sold_out"
        if sale_status == "ON_SALE":
            return "on_sale"
        if sale_status == "COMING_SOON":
            return "coming_soon"
        
        return "unknown"

    def _get_api_data(self, endpoint: str):
        try:
            url = f"{self.api_url}/{endpoint}"
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if not isinstance(data, (dict, list)):
                    logging.warning(f"Biletix API returned non-JSON data for {endpoint}: {str(data)[:100]}")
                    return None
                return data
            else:
                logging.debug(f"Biletix API status {res.status_code} for {endpoint}")
        except Exception as e:
            logging.debug(f"Biletix API error on {endpoint}: {e}")
        return None
