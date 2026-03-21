from datetime import datetime
import pytz

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
