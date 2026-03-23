import logging
from providers.kultur_istanbul import KulturIstanbulProvider

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def test():
    provider = KulturIstanbulProvider()
    events = provider.fetch_and_parse()
    print(f"Total events parsed: {len(events)}")
    for i, e in enumerate(events[:5]):
        print(f"{i}. {e.title}")
        for occ in e.occurrences:
            print(f"  - {occ.local_date} {occ.local_time} at {occ.venue_name}")
        for s in e.occurrences[0].sources:
            print(f"  - Price: {s.price.text if s.price else 'None'}")

if __name__ == "__main__":
    test()
