import requests
from bs4 import BeautifulSoup

url = "https://kultur.istanbul/etkinlikler/"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
res = requests.get(url, headers=headers)
soup = BeautifulSoup(res.text, 'html.parser')

cards = soup.select(".wpem-event-layout-column")
print(f"Items found with .wpem-event-layout-column: {len(cards)}")

# Try alternative selector
alt_cards = soup.select(".wpem-event-box-col")
print(f"Items found with .wpem-event-box-col: {len(alt_cards)}")

alt2 = soup.select(".event-box")
print(f"Items found with .event-box: {len(alt2)}")

if len(cards) == 0:
    print("Maybe the page relies on javascript or uses different classes:")
    # Print out some classes of divs inside the list wrapper
    wrappers = soup.select("div.wpem-event-listings")
    if wrappers:
        print("Found wpem-event-listings container")
        for child in wrappers[0].find_all('div', recursive=False):
            print("Child classes:", child.get('class'))
    else:
        print("No wpem-event-listings container found")
