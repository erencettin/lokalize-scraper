from bs4 import BeautifulSoup

with open('artifacts/probes/etkinlik_raw.html', 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f, 'html.parser')

print("--- Searching for 'JJ Pub Kanyon' ---")
venue_els = soup.find_all(string=lambda t: "JJ Pub Kanyon" in t)
for el in venue_els:
    parent = el.parent
    print(f"Text in: <{parent.name} class='{parent.get('class')}'>")
    print(f"Parent of Parent: <{parent.parent.name} class='{parent.parent.get('class')}'>")

print("\n--- Searching for '23 Mart' ---")
date_els = soup.find_all(string=lambda t: "23 Mart" in t)
for el in date_els:
    parent = el.parent
    print(f"Text in: <{parent.name} class='{parent.get('class')}'>")
    print(f"Parent of Parent: <{parent.parent.name} class='{parent.parent.get('class')}'>")

print("\n--- Searching for '20:00' ---")
time_els = soup.find_all(string=lambda t: "20:00" in t)
for el in time_els:
    parent = el.parent
    print(f"Text in: <{parent.name} class='{parent.get('class')}'>")
