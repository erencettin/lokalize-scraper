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

_CATEGORY_LABELS = {
    "concert":   "🎵 Konser & Müzik",
    "theatre":   "🎭 Tiyatro & Sahne",
    "standup":   "🎤 Stand-up & Komedi",
    "festival":  "🎪 Festival",
    "cinema":    "🎬 Sinema",
    "exhibition":"🖼️ Sergi & Sanat",
    "experience":"🎨 Atölye & Deneyim",
    "show":      "🎙️ Söyleşi & Gösteri",
    "sports":    "⚽ Spor",
    "family":    "👨‍👩‍👧 Aile & Çocuk",
}


def _format_date(iso: str | None) -> str:
    if not iso:
        return "?"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        months = ["Oca", "Şub", "Mar", "Nis", "May", "Haz",
                  "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
        return f"{dt.day} {months[dt.month - 1]} {dt.year}"
    except Exception:
        return iso[:10]


def _build_markdown(report: Dict[str, Any]) -> str:
    generated_at = report.get("generatedAt", "")
    try:
        dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        date_str = _format_date(generated_at)
    except Exception:
        date_str = generated_at[:10]

    lines: list[str] = [
        f"# 📅 Haftalık Trend Raporu — {date_str}",
        f"",
        f"> Son {report.get('lookbackDays', 14)} günün Google Trends verisine göre Türkiye'de öne çıkan etkinlik kategorileri ve şehirlerdeki etkinlikler.",
        f"> **{report.get('requestCount', 0)} SerpAPI isteği kullanıldı.**",
        f"",
        f"---",
        f"",
    ]

    for city, candidates in report.get("cities", {}).items():
        lines.append(f"## 📍 {city.upper()}")
        lines.append("")

        if not candidates:
            lines.append("_Bu hafta eşleşen trend bulunamadı._")
            lines.append("")
            continue

        for candidate in candidates:
            category = candidate.get("category", "")
            label = _CATEGORY_LABELS.get(category, f"🔹 {category}")
            term = candidate.get("term", "")
            score = candidate.get("trendScore", 0)
            events = candidate.get("events", [])

            lines.append(f"### {label}")
            lines.append(f'> Trend: **"{term}"** &nbsp;|&nbsp; Skor: `{score}`')
            lines.append("")

            if events:
                for ev in events:
                    title = ev.get("title", "").strip()
                    url = ev.get("sourceUrl") or ""
                    date = _format_date(ev.get("nextDate"))
                    if url:
                        lines.append(f"- [{title}]({url}) — {date}")
                    else:
                        lines.append(f"- {title} — {date}")
            else:
                lines.append("_Sistemde bu kategoride yaklaşan etkinlik bulunamadı._")

            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


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
    _logger.info("JSON raporu kaydedildi: %s", output_path)

    md_path = output_path.with_suffix(".md")
    md_path.write_text(_build_markdown(payload), encoding="utf-8")
    _logger.info("Markdown raporu kaydedildi: %s", md_path)


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
