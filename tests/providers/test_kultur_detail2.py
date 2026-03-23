import requests
from bs4 import BeautifulSoup

url = "https://kultur.istanbul/etkinlik/dusler-zamani-japonya/"
headers = {"User-Agent": "Mozilla/5.0"}
res = requests.get(url, headers=headers)
soup = BeautifulSoup(res.text, 'html.parser')

print("Date text:", [d.text.strip() for d in soup.select(".wpem-event-date-time span, .wpem-event-date-text, .wpem-event-time-text")])
print("Venue text:", [v.text.strip() for v in soup.select(".wpem-event-location span, .wpem-single-event-location")])
print("Price text:", [p.text.strip() for p in soup.select(".wpem-event-type-text, .wpem-ticket-price")])
