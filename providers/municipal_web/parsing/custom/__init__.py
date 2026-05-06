"""Custom municipal parser exports."""

from providers.municipal_web.parsing.custom.bagcilar import BagcilarParser
from providers.municipal_web.parsing.custom.bakirkoy import BakirkoyParser
from providers.municipal_web.parsing.custom.kartal import KartalParser
from providers.municipal_web.parsing.custom.silivri import SilivriParser

__all__ = [
    "BagcilarParser",
    "BakirkoyParser",
    "KartalParser",
    "SilivriParser",
]
