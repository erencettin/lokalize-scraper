import requests

url = "https://kultur.istanbul/wp-admin/admin-ajax.php"
headers = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/x-www-form-urlencoded"
}
data = {
    "action": "get_event_listings",
    "search_keywords": "",
    "per_page": "50",
    "paged": "1"
}

res = requests.post(url, headers=headers, data=data)
print(f"Status: {res.status_code}")
try:
    j = res.json()
    html_content = j.get('html', '')
    if html_content:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        cards = soup.select(".wpem-event-layout-column")
        print(f"Found cards in AJAX html: {len(cards)}")
        if len(cards) > 0:
            print("First item title:", cards[0].select_one('.wpem-heading-text').text.strip())
    else:
        print("No HTML in JSON response")
except Exception as e:
    print("Error parsing JSON or HTML", e)
    print("Response text snippet:", res.text[:200])
