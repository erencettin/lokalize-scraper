import logging
from typing import List, Optional
from datetime import datetime
import pytz
import json
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from providers.base_provider import BaseProvider
from models.normalized_event import NormalizedEvent, NormalizedOccurrence, NormalizedSource, PriceInfo
from utils.date_parser import DateParser

class PassoProvider(BaseProvider):
    """
    Provider for Passo (passo.com.tr) event platform.
    Uses a headless Playwright Chromium session to POST to the internal JSON API.
    """

    API_BASE = "https://ticketingweb.passo.com.tr/api/passoweb"
    LANGUAGE_ID = 118  # Turkish
    PAGE_SIZE = 100
    MAX_EVENTS = 2500  # Increased to cover all Istanbul events (~2200)
    CITY_ID_ISTANBUL = 101 # int, verified working in probe

    CATEGORY_MAP = {
        "Müzik": "concert",
        "Tiyatro": "theatre",
        "Spor": "match",
        "Sanat": "experience",
        "Çocuk": "show",
        "Eğitim": "experience",
        "Sinema": "cinema",
        "Festival": "festival",
        "Stand-Up": "standup",
        "Sergi": "exhibition",
    }

    def __init__(self):
        super().__init__(name="Passo", mode="browser")
        self._date_parser = DateParser()
        self._tz = pytz.timezone("Europe/Istanbul")

    def fetch_and_parse(self) -> List[NormalizedEvent]:
        logging.info("Starting Passo fetch_and_parse...")
        events = []
        raw_items = self._fetch_all_raw_events()
        logging.info(f"Passo: Found {len(raw_items)} raw events from API")

        for i, item in enumerate(raw_items):
            try:
                event = self._parse_event(item)
                if event:
                    events.append(event)
            except Exception as e:
                logging.error(f"Error parsing Passo event {item.get('id')}: {e}")

        logging.info(f"Passo: Parsed {len(events)} valid events")
        return events

    def _fetch_all_raw_events(self) -> list:
        all_items = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            try:
                logging.debug("Passo: Priming session via homepage visit...")
                page.goto("https://www.passo.com.tr/tr", wait_until="domcontentloaded")
                time.sleep(2)
            except PlaywrightTimeoutError:
                logging.warning("Passo: Homepage visit timed out; continuing anyway")

            from_idx = 0
            while from_idx < self.MAX_EVENTS:
                try:
                    payload = {
                        "CountRequired": True,
                        "HastagId": None,
                        "CityId": "101",
                        "date": None,
                        "VenueId": None,
                        "LanguageId": self.LANGUAGE_ID,
                        "from": from_idx,
                        "size": self.PAGE_SIZE
                    }
                    logging.info(f"Passo: Fetching events from={from_idx}")

                    result = page.evaluate("""async ([url, payload]) => {
                        const resp = await fetch(url, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'Accept': 'application/json',
                            },
                            body: JSON.stringify(payload)
                        });
                        return await resp.json();
                    }""", [f"{self.API_BASE}/allevents", payload])

                    if not result:
                        break

                    items = result.get("valueList", [])
                    total = result.get("totalItemCount", 0)

                    if not items:
                        break

                    all_items.extend(items)
                    logging.info(f"Passo: Fetched {len(items)} items (Total: {len(all_items)})")

                    if len(all_items) >= total or len(all_items) >= self.MAX_EVENTS:
                        break

                    from_idx += self.PAGE_SIZE
                    time.sleep(0.5)
                except Exception as e:
                    logging.error(f"Passo: Fetch error at from={from_idx}: {e}")
                    break

            browser.close()
        return all_items

    def _parse_event(self, item: dict) -> Optional[NormalizedEvent]:
        event_id = item.get("id")
        title = item.get("name", "").strip()
        seo_url = item.get("seoUrl", "")
        
        if not event_id or not title:
            return None

        raw_date = item.get("date") or item.get("startDate")
        start_at_utc = self._parse_date(raw_date)
        if not start_at_utc:
            return None

        venue_name = item.get("venueName", "Passo Venue").strip()
        genres = item.get("eventGroupGenreList") or []
        category = "experience"
        for genre in genres:
            genre_name = genre.get("genreName", "")
            if genre_name in self.CATEGORY_MAP:
                category = self.CATEGORY_MAP[genre_name]
                break

        local_dt = start_at_utc.astimezone(self._tz)
        image_url = item.get("homePageImagePath") or item.get("imagePath")
        if image_url and not image_url.startswith("http"):
             image_url = f"https://image.passo.com.tr/{image_url}"

        min_price = item.get("minPrice") or item.get("minAmount")
        if min_price and min_price > 5000:
            min_price = min_price / 100

        source = NormalizedSource(
            provider="Passo",
            external_id=str(event_id),
            source_url=f"https://www.passo.com.tr/tr/etkinlik/{seo_url}",
            price=PriceInfo(
                text=f"{min_price:.2f} TL" if min_price else "Fiyat bilgisi yok",
                min_value=float(min_price) if min_price else None,
            ),
            ticket_status="on_sale",
            title=title,
        )

        occurrence = NormalizedOccurrence(
            venue_name=venue_name,
            start_at_utc=start_at_utc,
            local_date=local_dt.strftime("%Y-%m-%d"),
            local_time=local_dt.strftime("%H:%M"),
            sources=[source],
        )

        return NormalizedEvent(
            title=title,
            description=item.get("seoDescription") or "",
            type=category,
            city_name="Istanbul",
            image_url=image_url,
            occurrences=[occurrence],
        )

    def _parse_date(self, raw: str) -> Optional[datetime]:
        if not raw or raw.startswith("0001-01-01"):
            return None
        try:
            # Use the specific ISO parser from the global utility
            result = self._date_parser.parse_iso_date(raw)
            if result:
                # result is already UTC aware from parse_iso_date
                return result
        except Exception:
            pass
        return None
