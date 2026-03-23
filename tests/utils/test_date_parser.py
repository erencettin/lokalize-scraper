from utils.date_parser import DateParser

val = DateParser.parse_turkish_date("23 Mart 2026, 20:30")
print(f"Parsed: {val}")
val2 = DateParser.parse_turkish_date("23 Mart 2026, 20:30a tanık ola")
print(f"Parsed2: {val2}")
