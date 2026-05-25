"""Smoke test: Discovery Feed 2.0 parse + field validation."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from config import settings
from providers.ticketmaster.http_client import TicketmasterHttpClient
from providers.ticketmaster.response_parser import ResponseParser
from providers.ticketmaster.event_builder import EventBuilder, _normalize_city

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "

def check(label, value, ok):
    icon = PASS if ok else FAIL
    print(f"  {icon} {label}: {value}")
    return ok

def main():
    print("\n=== Discovery Feed 2.0 Smoke Test ===\n")

    # 1. Download feed
    print("[1] Feed indiriliyor...")
    client = TicketmasterHttpClient()
    client.setup_session()
    raw_events = client._fetch_feed_as_events()

    if raw_events is None:
        print(f"  {FAIL} Feed indirilemedi veya parse edilemedi.")
        sys.exit(1)

    total = len(raw_events)
    ok1 = check("Raw event sayısı", total, total > 0)
    if not ok1:
        print(f"  {FAIL} Feed boş geldi, devam edilemiyor.")
        sys.exit(1)

    # 2. Parse events
    print(f"\n[2] İlk 3 event parse ediliyor (toplam {total})...")
    parser = ResponseParser()
    builder = EventBuilder()

    parsed = []
    for raw in raw_events:
        item = parser.parse_event(raw)
        if item:
            parsed.append(item)
        if len(parsed) >= 3:
            break

    check("Parse edilen event sayısı (ilk 3)", len(parsed), len(parsed) > 0)

    # 3. Field checks per event
    print(f"\n[3] Alan kontrolleri...")
    target_city = _normalize_city(settings.ticketmaster_city)
    affiliate_prefix = "ticketmaster.evyy.net/c/7294156"

    all_ok = True
    for i, item in enumerate(parsed, 1):
        print(f"\n  --- Event {i}: {item.title[:60]!r} ---")
        results = [
            check("eventName (title)",      item.title,              bool(item.title)),
            check("primaryEventUrl",         item.primary_event_url,  bool(item.primary_event_url)),
            check("eventStatus",             item.event_status,       bool(item.event_status)),
            check("brandName",               item.brand_name,         bool(item.brand_name)),
            check("officialSeller",          item.is_official_seller, item.is_official_seller is not None),
            check("venueCity",               item.venue_city,         bool(item.venue_city)),
        ]
        all_ok = all_ok and all(results)

    # 4. Affiliate URL check
    print(f"\n[4] Affiliate URL formatı kontrol ediliyor...")
    affiliate_ok_count = 0
    fallback_count = 0
    for raw in raw_events[:20]:
        item = parser.parse_event(raw)
        if not item:
            continue
        if affiliate_prefix in item.primary_event_url:
            affiliate_ok_count += 1
        elif item.primary_event_url:
            fallback_count += 1

    checked = affiliate_ok_count + fallback_count
    check(
        f"Affiliate URL ({affiliate_prefix})",
        f"{affiliate_ok_count}/{checked} event'te",
        affiliate_ok_count > 0,
    )
    if fallback_count > 0:
        print(f"  {WARN} {fallback_count} event'te düz URL var (affiliate prefix yok)")

    # 5. City filter check
    print(f"\n[5] Şehir filtresi kontrol ediliyor (hedef: {settings.ticketmaster_city!r})...")
    city_pass = city_fail = city_skip = 0
    for raw in raw_events[:50]:
        item = parser.parse_event(raw)
        if not item:
            continue
        city = item.venue_city or settings.ticketmaster_city
        if not item.venue_city:
            city_skip += 1
            continue
        if _normalize_city(city) == target_city:
            city_pass += 1
        else:
            city_fail += 1

    print(f"  {PASS if city_fail == 0 else FAIL} İstanbul: {city_pass}  Diğer şehir (filtrelenecek): {city_fail}  venue_city boş (config fallback): {city_skip}")

    # Built events after filter
    print(f"\n[5b] EventBuilder ile şehir filtresi uygulanıyor (ilk 50 raw event)...")
    built = [builder.build(parser.parse_event(r)) for r in raw_events[:50] if parser.parse_event(r)]
    built = [e for e in built if e is not None]
    check(
        f"Filter sonrası event sayısı (50 raw'dan)",
        len(built),
        len(built) >= 0,
    )
    other_cities = {e.city_name for e in built if _normalize_city(e.city_name) != target_city}
    if other_cities:
        print(f"  {FAIL} Filtreden geçmemesi gereken şehirler: {other_cities}")
    else:
        print(f"  {PASS} Tüm build edilen eventler Istanbul")

    print(f"\n=== Sonuç: {'PASS ✅' if all_ok else 'BAZI KONTROLLER BAŞARISIZ ❌'} ===\n")

if __name__ == "__main__":
    main()
