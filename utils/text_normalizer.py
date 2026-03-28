import re
import unicodedata


class TextNormalizer:
    @staticmethod
    def normalize_for_match(text: str) -> str:
        """
        Standard normalization for string comparison:
        - Fix common mojibake when possible
        - Lowercase
        - Strip whitespace
        - Normalize unicode characters (remove accents)
        - Remove non-alphanumeric noise
        """
        if not text:
            return ""

        text = TextNormalizer._fix_mojibake(text)

        # Convert to lowercase and strip
        text = text.lower().strip()

        # Normalize Turkish characters to ASCII
        text = (
            text.replace("\u0131", "i")
            .replace("\u0307", "")
            .replace("\u011f", "g")
            .replace("\u00fc", "u")
            .replace("\u015f", "s")
            .replace("\u00f6", "o")
            .replace("\u00e7", "c")
        )

        # Normalize unicode (NFD) and filter out non-spacing marks
        text = "".join(
            c for c in unicodedata.normalize("NFD", text)
            if unicodedata.category(c) != "Mn"
        )

        # Remove punctuation/noise using regex
        text = re.sub(r"[^\w\s]", "", text)

        # Collapse multiple spaces
        text = re.sub(r"\s+", " ", text).strip()

        return text

    @staticmethod
    def generate_logical_key(title: str, city: str) -> str:
        """
        Generates a stable, deterministic key for grouping event occurrences.
        Format: type-title-city (e.g., concert-duman-istanbul)
        """
        norm_title = TextNormalizer.normalize_for_match(title).replace(" ", "-")
        norm_city = TextNormalizer.normalize_for_match(city).replace(" ", "-")
        return f"{norm_title}-{norm_city}"

    @staticmethod
    def generate_fingerprint(title: str, venue: str, local_date: str, local_time: str) -> str:
        """
        Generates a unique fingerprint for a specific occurrence (Event + Date + Venue).
        """
        norm_title = TextNormalizer.normalize_for_match(title)
        norm_venue = TextNormalizer.normalize_for_match(venue)
        return f"{norm_title}|{norm_venue}|{local_date}|{local_time}"

    @staticmethod
    def _fix_mojibake(text: str) -> str:
        if not text:
            return text

        # Heuristic: if mojibake markers exist, try Latin1 -> UTF8 repair.
        if "\u00c3" not in text and "\u00c4" not in text and "\u00c5" not in text:
            return text

        try:
            return text.encode("latin1").decode("utf-8")
        except UnicodeError:
            return text
