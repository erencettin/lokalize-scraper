import requests
from bs4 import BeautifulSoup

url = "https://kultur.istanbul/etkinlikler/"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
res = requests.get(url, headers=headers)
soup = BeautifulSoup(res.text, 'html.parser')

with open("kultur_html.txt", "w", encoding="utf-8") as f:
    f.write(soup.prettify())
