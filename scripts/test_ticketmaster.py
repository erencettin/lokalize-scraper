import os
import sys
from collections import Counter

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from providers.ticketmaster import TicketmasterProvider


def main() -> None:
    provider = TicketmasterProvider()
    events = provider.fetch_and_parse()

    print(f"Toplam event: {len(events)}")

    category_counter = Counter()
    for event in events:
        category_counter[event.type] += 1

    print("\nKategori dagilimi:")
    for category, count in category_counter.most_common():
        print(f"- {category}: {count}")

    print("\nOrnek eventler:")
    for event in events[:5]:
        first_occurrence = event.occurrences[0] if event.occurrences else None
        when = (
            f"{first_occurrence.local_date} {first_occurrence.local_time}"
            if first_occurrence
            else "tarih yok"
        )
        venue = first_occurrence.venue_name if first_occurrence else "mekan yok"
        print(f"- {event.title} | {event.type} | {when} | {venue}")


if __name__ == "__main__":
    main()
