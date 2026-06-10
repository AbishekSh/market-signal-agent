from __future__ import annotations

import requests

from app.schemas import AnalysisResult, ExtractedFact, FilingMetadata, Intent, TelegramStatus


DEFAULT_RESEARCH_MESSAGE = "Analyze SpaceX prospectus ahead of the IPO"


def extract_message(update: dict) -> tuple[str | None, str | None]:
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    text = message.get("text")
    chat_id = chat.get("id")
    return (str(chat_id) if chat_id is not None else None, normalize_message_text(text))


def normalize_message_text(text: str | None) -> str | None:
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("/start"):
        parts = stripped.split(maxsplit=1)
        return parts[1].strip() if len(parts) > 1 else DEFAULT_RESEARCH_MESSAGE
    if stripped.startswith("/research"):
        parts = stripped.split(maxsplit=1)
        return parts[1].strip() if len(parts) > 1 else DEFAULT_RESEARCH_MESSAGE
    return stripped


def build_telegram_summary(
    intent: Intent,
    filing: FilingMetadata | None,
    facts: list[ExtractedFact],
    analysis: AnalysisResult,
    warnings: list[str],
    errors: list[str],
    report_name: str,
) -> str:
    company = filing.company_name if filing else (intent.likely_formal_company_name or intent.company_name)
    if errors:
        return (
            f"{company}: research run could not complete.\n"
            f"Error: {errors[0]}\n"
            "Try again after checking the SEC lookup/app logs."
        )[:1200]

    fact_map = {fact.metric: fact for fact in facts if fact.value is not None}
    metric_map = {metric.metric: metric for metric in analysis.metrics}
    filing_line = "No filing selected."
    if filing:
        filing_line = f"{filing.form} filed {filing.filing_date}, accession {filing.accession_number}"

    lines = [
        f"{company} research summary",
        filing_line,
        "",
        f"Revenue: {_fact_value(fact_map, 'revenue') or 'unavailable'}",
        f"Operating margin: {_metric_value(metric_map, 'operating_margin') or 'unavailable'}",
        f"Net margin: {_metric_value(metric_map, 'net_margin') or 'unavailable'}",
        f"Cash: {_fact_value(fact_map, 'cash') or 'unavailable'}",
        f"Liquidity: {_metric_value(metric_map, 'liquidity') or 'unavailable'}",
        f"Capex intensity: {_metric_value(metric_map, 'capex_intensity') or 'unavailable'}",
        "",
        "Takeaway: scale is substantial, but the extracted period shows negative profitability and heavy capital intensity.",
    ]
    if warnings:
        lines.extend(["", f"Caveat: {warnings[0]}"])
    if report_name:
        lines.extend(["", f"Saved report: {report_name}"])
    return "\n".join(lines)[:1200]


def send_telegram_summary(token: str, chat_id: str | None, text: str) -> TelegramStatus:
    if not token:
        return TelegramStatus(status="skipped", detail="TELEGRAM_BOT_TOKEN is not configured.")
    if not chat_id:
        return TelegramStatus(status="skipped", detail="No Telegram chat_id was provided.")
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:3900]},
            timeout=15,
        )
        response.raise_for_status()
        return TelegramStatus(status="sent", detail=f"Sent to chat {chat_id}")
    except Exception as exc:
        return TelegramStatus(status="error", detail=str(exc))


def _fact_value(facts: dict[str, ExtractedFact], name: str) -> str:
    fact = facts.get(name)
    if not fact or fact.value is None:
        return ""
    return f"{fact.value:,.0f} {fact.unit}".strip()


def _metric_value(metrics: dict[str, object], name: str) -> str:
    metric = metrics.get(name)
    value = getattr(metric, "value", None)
    status = getattr(metric, "status", "")
    unit = getattr(metric, "unit", "")
    if value is None or status == "missing":
        return ""
    return f"{value:,.2f} {unit}".strip()
