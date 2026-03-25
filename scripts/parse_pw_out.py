with open("artifacts/probes/passo_discovered_requests.txt", "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()

with open("artifacts/probes/passo_req_clean.txt", "w", encoding="utf-8") as out:
    for line in lines:
        out.write(line)

print(f"Total lines: {len(lines)}")
for line in lines:
    print(repr(line.strip()))
