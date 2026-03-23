import requests
from bs4 import BeautifulSoup

url = "https://kultur.istanbul/etkinlik/dusler-zamani-japonya/"
headers = {"User-Agent": "Mozilla/5.0"}
res = requests.get(url, headers=headers)
soup = BeautifulSoup(res.text, 'html.parser')

print("Checking detail page for dates:")

date_els = soup.select(".wpem-event-date-text")
print(f"wpem-event-date-text elements: {len(date_els)}")
for d in date_els:
    print(d.text.strip())

date_els2 = soup.select(".wpem-event-time-text")
for d in date_els2:
    print(d.text.strip())

date_wrapper = soup.select(".wpem-event-date-time")
for d in date_wrapper:
    print("Wrapper text:", d.text.strip())
