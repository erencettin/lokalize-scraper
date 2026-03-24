import re
from typing import Tuple, Optional

class PriceParser:
    @staticmethod
    def parse_prices(price_text: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Parses min and max values from price strings like:
        - "₺850" -> (850.0, 850.0)
        - "₺500 - ₺1200" -> (500.0, 1200.0)
        - "Ücretsiz" -> (0.0, 0.0)
        """
        if not price_text:
            return None, None
            
        # Handle "Free" / "Ücretsiz"
        if any(word in price_text.lower() for word in ["ücretsiz", "free", "0", "bedava"]):
            return 0.0, 0.0
            
        # Extract all numbers/decimals
        # Matches patterns like 850, 1.200, 1200.50
        numbers = re.findall(r"(\d+(?:[.,]\d+)?)", price_text.replace(".", "").replace(",", "."))
        
        if not numbers:
            return None, None
            
        float_vals = sorted([float(n) for n in numbers])
        
        if len(float_vals) == 1:
            return float_vals[0], float_vals[0]
        else:
            return float_vals[0], float_vals[-1]
