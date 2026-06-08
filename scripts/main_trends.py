"""Entry point for the weekly trend-analysis report ("this week in your city" Instagram posts)."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import settings
from services.trend_analysis_service import TrendAnalysisService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
_logger = logging.getLogger(__name__)


def _save_report(report: Dict[str, Any]) -> None:
    output_path = _ROOT / settings.trends_output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "lookbackDays": settings.trends_lookback_days,
        **report,
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _logger.info("Saved trend report to %s", output_path)


def main() -> int:
    _logger.info("=== Trend analysis started ===")

    if not settings.trends_enabled:
        _logger.warning("TRENDS_ENABLED=false — exiting without making requests")
        return 0

    service = TrendAnalysisService()
    report = service.build_report()
    _save_report(report)

    _logger.info(
        "=== Trend analysis finished — %s SerpAPI requests used ===",
        report.get("requestCount", 0),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
