import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import pytz
import html
import time
import random
import re
from typing import List, Optional, Set, Tuple
from models.normalized_event import NormalizedEvent, NormalizedOccurrence, NormalizedSource, PriceInfo
from providers.base_provider import BaseProvider
from utils.date_parser import DateParser


class EtkinlikIoProvider(BaseProvider):
    """
    Production-ready Etkinlik.io provider using multi-feed RSS deep crawl.
    Uses robust Meta Tag extraction (OG / Event meta tags) for detail pages.
    """

    RSS_BASE_URL = "https://etkinlik.io/rss/sorgu"
    MAX_RETRIES = 2

    CITY_IDS = {
        "İstanbul": 40,
        "Ankara": 6,
        "İzmir": 41,
        "Antalya": 7,
        "Bursa": 16,
        "Eskişehir": 26,
    }

    TYPE_IDS = {
        "Atölye": 1, "Çocuk": 3, "Konser": 4, "Sahne Sanatları": 5, "Spor": 7, "Sergi": 8, "Festival": 9,
    }

    def __init__(self):
        super().__init__("Etkinlik.io", mode="http")
        self.base_url = "https://etkinlik.io"
        self.logger = logging.getLogger(__name__)
        self.session: Optional[requests.Session] = None

    def _setup_session(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        })

    def fetch_and_parse(self) -> List[NormalizedEvent]:
        self._setup_session()
        self.logger.info("Starting Etkinlik.io Deep Crawl (Meta-Tag Extraction)...")

        discovered = {}  # url -> {title, category, city_name}
        self._collect_from_feeds(discovered)
        self.logger.info(f"Phase 1 complete: {len(discovered)} unique events discovered.")

        events = []
        total = len(discovered)
        for i, (url, meta) in enumerate(discovered.items(), 1):
            event = self._scrape_detail_page(url, meta)
            if event:
                events.append(event)
            
            if i % 25 == 0:
                self.logger.info(f"  [{i}/{total}] Scraped {len(events)} events...")
            
            time.sleep(random.uniform(0.5, 1.0))

        self.logger.info(f"Etkinlik.io complete. Total events: {len(events)}")
        return events

    def _collect_from_feeds(self, discovered: dict):
        feed_queries = [("Base", {})]
        for name, cid in self.CITY_IDS.items():
            feed_queries.append((f"City:{name}", {"sehirIds": str(cid)}))
        for name, tid in self.TYPE_IDS.items():
            feed_queries.append((f"Type:{name}", {"turIds": str(tid)}))
            feed_queries.append((f"İstanbul+{name}", {"sehirIds": "40", "turIds": str(tid)}))

        for label, params in feed_queries:
            try:
                resp = self.session.get(self.RSS_BASE_URL, params=params, timeout=12)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.content, 'xml')
                for item in soup.find_all('item'):
                    link = item.find('link').text.strip()
                    if link not in discovered:
                        discovered[link] = {
                            "title": html.unescape(item.find('title').text.strip()),
                            "category": item.find('category').text.strip() if item.find('category') else "Diğer",
                            "city_name": label.split("City:")[1] if "City:" in label else "İstanbul"
                        }
            except Exception as e:
                self.logger.debug(f"Feed {label} failed: {e}")

    def _scrape_detail_page(self, url: str, meta: dict) -> Optional[NormalizedEvent]:
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200: return None
            
            soup = BeautifulSoup(resp.text, 'html.parser')

            # 1. Date (Robust Meta Tag)
            start_time_meta = soup.find("meta", property=re.compile(r"event:start_time|og:event:start_time"))
            if not start_time_meta:
                start_time_meta = soup.find("meta", {"name": "event:start_time"})
            
            if not start_time_meta or not start_time_meta.get('content'):
                return None
            
            start_at_utc = DateParser.parse_iso_date(start_time_meta['content'])
            if not start_at_utc: return None

            # 2. Venue & City (Robust Keywords Meta)
            venue_name = "Belirtilmemiş"
            city_name = meta.get("city_name", "İstanbul")
            kw_meta = soup.find("meta", {"name": "keywords"})
            if kw_meta:
                kws = [k.strip() for k in kw_meta['content'].split(',')]
                # Format: [Type, Category, ..., Venue, City]
                if len(kws) >= 2:
                    venue_name = kws[-2]
                    city_name = kws[-1]
            elif meta.get("city_name"):
                 city_name = meta["city_name"]

            # 3. Image & Description
            img_meta = soup.find("meta", property="og:image")
            image_url = img_meta['content'] if img_meta else None
            
            desc_meta = soup.find("meta", property="og:description") or soup.find("meta", {"name": "description"})
            description = desc_meta['content'] if desc_meta else ""

            # 4. Pricing & Ticket
            bilet_btn = soup.select_one('#link_bilet_al')
            ticket_url = bilet_btn['href'] if bilet_btn and bilet_btn.has_attr('href') else url
            if not ticket_url.startswith('http'): ticket_url = self.base_url + ticket_url

            price_badge = soup.select_one('.badge-ucret')
            price_text = price_badge.get_text(strip=True) if price_badge else ("Ücretsiz" if "Ücretsiz" in description else "Bilinmiyor")

            # Finalize
            local_date, local_time, tz = DateParser.to_local_parts(start_at_utc)
            source = NormalizedSource(
                provider=self.name, external_id=url.rstrip('/').split('/')[-1],
                title=meta["title"], source_url=ticket_url, price=PriceInfo(text=price_text)
            )
            occurrence = NormalizedOccurrence(
                start_at_utc=start_at_utc, local_date=local_date, local_time=local_time,
                timezone=tz, venue_name=venue_name, sources=[source]
            )
            return NormalizedEvent(
                title=meta["title"], description=description[:2000],
                type=self._resolve_type(meta["category"]),
                city_name=city_name, image_url=image_url, occurrences=[occurrence]
            )

        except Exception as e:
            self.logger.debug(f"Failed to scrape {url}: {e}")
            return None

    def _resolve_type(self, category_str: str) -> str:
        cat = category_str.lower()
        mapping = {
            "konser": "concert", "müzik": "concert", "tiyatro": "theatre", "sahne": "theatre",
            "stand-up": "standup", "stand up": "standup", "spor": "match", "festival": "festival",
            "atölye": "experience", "sergi": "experience", "gezi": "experience", "çocuk": "show",
            "sinema": "cinema", "film": "cinema", "yemek": "food_offer"
        }
        for k, v in mapping.items():
            if k in cat: return v
        return "show"
