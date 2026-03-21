import re
import unicodedata

class TextNormalizer:
    @staticmethod
    def normalize_for_match(text: str) -> str:
        """
        Standard normalization for string comparison:
        - Lowercase
        - Strip whitespace
        - Normalize unicode characters (remove accents)
        - Remove non-alphanumeric noise
        """
        if not text:
            return ""
        
        # Convert to lowercase and strip
        text = text.lower().strip()
        
        # Replace Turkish characters properly before general normalization
        text = text.replace('ı', 'i').replace('ü', 'u').replace('ö', 'o').replace('ş', 's').replace('ç', 'c').replace('ğ', 'g')
        
        # Normalize unicode (NFD) and filter out non-spacing marks
        text = "".join(
            c for c in unicodedata.normalize('NFD', text)
            if unicodedata.category(c) != 'Mn'
        )
        
        # Remove punctuation/noise using regex
        text = re.sub(r'[^\w\s]', '', text)
        
        # Collapse multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    @staticmethod
    def generate_logical_key(title: str, city: str) -> str:
        """
        Generates a stable, deterministic key for grouping event occurrences.
        Format: type-title-city (e.g., concert-duman-istanbul)
        """
        norm_title = TextNormalizer.normalize_for_match(title).replace(' ', '-')
        norm_city = TextNormalizer.normalize_for_match(city).replace(' ', '-')
        return f"{norm_title}-{norm_city}"

    @staticmethod
    def generate_fingerprint(title: str, venue: str, local_date: str, local_time: str) -> str:
        """
        Generates a unique fingerprint for a specific occurrence (Event + Date + Venue).
        """
        norm_title = TextNormalizer.normalize_for_match(title)
        norm_venue = TextNormalizer.normalize_for_match(venue)
        return f"{norm_title}|{norm_venue}|{local_date}|{local_time}"
