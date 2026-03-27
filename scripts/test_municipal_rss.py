import os
import sys
from collections import Counter

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from providers.municipal_rss import MunicipalRssProvider


def main() -> None:
    provider = MunicipalRssProvider()
    events = provider.fetch_and_parse()

    print(f"Toplam event: {len(events)}")
    categories = Counter(event.type for event in events)

    print("\nKategori dagilimi:")
    for category, count in categories.most_common():
        print(f"- {category}: {count}")

    print("\nOrnek eventler:")
    for event in events[:5]:
        first = event.occurrences[0] if event.occurrences else None
        when = f"{first.local_date} {first.local_time}" if first else "tarih yok"
        venue = first.venue_name if first else "mekan yok"
        print(f"- {event.title} | {event.type} | {when} | {venue}")


if __name__ == "__main__":
    main()
