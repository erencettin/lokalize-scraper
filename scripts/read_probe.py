with open("probe_clean.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()
for line in lines:
    print(repr(line.strip()))
