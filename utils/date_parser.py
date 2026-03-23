from datetime import datetime
from typing import Optional
import pytz
import re

class DateParser:
    @staticmethod
    def parse_with_timezone(date_str: str, format_str: str, tz_name: str = "Europe/Istanbul") -> datetime:
        """
        Parses a date string and converts it to a timezone-aware UTC datetime.
        """
        local_tz = pytz.timezone(tz_name)
        # Parse as naive
        naive_dt = datetime.strptime(date_str, format_str)
        # Localize
        local_dt = local_tz.localize(naive_dt)
        # Convert to UTC
        return local_dt.astimezone(pytz.UTC)

    @staticmethod
    def parse_turkish_date(date_str: str, tz_name: str = "Europe/Istanbul") -> Optional[datetime]:
        """
        Parses Turkish date strings like:
        - "22 Mart 2026, Pazar 14:00"
        - "25 Nisan 2026, Cuma"
        """
        months = {
            "Ocak": 1, "Şubat": 2, "Mart": 3, "Nisan": 4, "Mayıs": 5, "Haziran": 6,
            "Temmuz": 7, "Ağustos": 8, "Eylül": 9, "Ekim": 10, "Kasım": 11, "Aralık": 12
        }
        
        try:
            # Clean up: "22 Mart 2026, Pazar 14:00" -> "22 3 2026 14:00"
            for m_name, m_num in months.items():
                if m_name in date_str:
                    date_str = date_str.replace(m_name, str(m_num))
                    break
            
            # Remove commas
            date_str = date_str.replace(',', '').strip()
            # Remove day names (Pazar, Cuma etc)
            date_str = re.sub(r'[A-Za-zçşığüöÇŞİĞÜÖ]+', '', date_str).strip()
            
            # Now we should have something like "22   3 2026  14:00"
            parts = [p for p in date_str.split() if p.strip()]
            
            if len(parts) >= 4: # Has time
                clean_str = f"{parts[0].zfill(2)} {parts[1].zfill(2)} {parts[2]} {parts[-1]}"
                return DateParser.parse_with_timezone(clean_str, "%d %m %Y %H:%M", tz_name)
            elif len(parts) == 3: # No time, assume 00:00
                clean_str = f"{parts[0].zfill(2)} {parts[1].zfill(2)} {parts[2]} 00:00"
                return DateParser.parse_with_timezone(clean_str, "%d %m %Y %H:%M", tz_name)
                
        except Exception as e:
            # If fail, returns None for provider to handle
            return None
        
        return None

    @staticmethod
    def parse_iso_date(iso_str: str) -> Optional[datetime]:
        """
        Parses ISO 8601 strings and returns a timezone-aware UTC datetime.
        Supports formats like:
        - "2026-03-23T20:00:00+00:00"
        - "2026-03-23T20:00:00Z"
        """
        try:
            # Handle Z suffix
            if iso_str.endswith('Z'):
                iso_str = iso_str.replace('Z', '+00:00')
            
            dt = datetime.fromisoformat(iso_str)
            # Ensure it's UTC aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=pytz.UTC)
            return dt.astimezone(pytz.UTC)
        except Exception:
            return None

    @staticmethod
    def to_local_parts(utc_dt: datetime, tz_name: str = "Europe/Istanbul"):
        """
        Converts UTC datetime back to local date and time strings.
        Returns: (date_str YYYY-MM-DD, time_str HH:MM, tz_name)
        """
        local_tz = pytz.timezone(tz_name)
        local_dt = utc_dt.astimezone(local_tz)
        return (
            local_dt.strftime("%Y-%m-%d"),
            local_dt.strftime("%H:%M"),
            tz_name
        )
