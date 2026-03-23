with open('artifacts/probes/etkinlik_raw.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "JJ Pub Kanyon" in line:
        print(f"--- VENUE FOUND at line {i+1} ---")
        print(lines[i-2:i+3])
    if "23 Mart" in line:
        print(f"--- DATE FOUND at line {i+1} ---")
        print(lines[i-2:i+3])
