import requests
from bs4 import BeautifulSoup

url = "https://etkinlik.io/rss/sorgu?sehirIds=40"
r = requests.get(url)
soup = BeautifulSoup(r.content, "xml")
items = soup.find_all("item")
print(f"Total items in RSS: {len(items)}")
for i, item in enumerate(items[:10]):
    link = item.find("link").text
    title = item.find("title").text
    print(f"[{i}] {title} -> {link}")
