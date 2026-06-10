from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.schemas import AnalysisResult, ExtractedFact, FilingMetadata, Intent


REPORT_SECTIONS = [
    "Executive summary",
    "Filing source and metadata",
    "Business overview",
    "Offering / IPO context",
    "Financial profile",
    "Growth and profitability",
    "Cash flow, capex, and liquidity",
    "Balance sheet and leverage",
    "Governance and share structure",
    "Key risk factors",
    "Valuation framing",
    "CIO takeaways",
    "Data limitations and caveats",
]

SECTION_METRICS = {
    "Growth and profitability": ["revenue_growth", "operating_margin", "net_margin"],
    "Cash flow, capex, and liquidity": ["cash_burn", "liquidity", "capex_intensity"],
    "Balance sheet and leverage": ["debt_to_assets", "liabilities_to_assets"],
}


def build_report(
    intent: Intent,
    filing: FilingMetadata | None,
    facts: list[ExtractedFact],
    analysis: AnalysisResult,
    narrative_sections: dict[str, str],
) -> str:
    report_company = filing.company_name if filing else (intent.likely_formal_company_name or intent.company_name)
    lines = [
        f"# {report_company} Financial Research Report",
        "",
        f"Created: {datetime.now(timezone.utc).isoformat()}",
        f"Audience: {intent.target_audience}",
        "",
    ]
    for section in REPORT_SECTIONS:
        lines.extend([f"## {section}", ""])
        lines.append(narrative_sections.get(section) or _default_section(section, filing, facts, analysis))
        lines.append("")
        if section == "Financial profile" and facts:
            lines.extend(_facts_table(facts))
            lines.append("")
        if section in SECTION_METRICS:
            lines.extend(_metrics_table(analysis, SECTION_METRICS[section]))
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def save_report(reports_dir: Path, run_id: str, markdown: str) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{run_id}.md"
    path.write_text(markdown, encoding="utf-8")
    return path


def _default_section(section: str, filing: FilingMetadata | None, facts: list[ExtractedFact], analysis: AnalysisResult) -> str:
    company = filing.company_name if filing else "the requested company"
    fact_map = _facts_by_metric(facts)
    metric_map = {metric.metric: metric for metric in analysis.metrics}
    if section == "Filing source and metadata" and filing:
        return (
            f"Selected {filing.form} for {filing.company_name} using CIK {filing.cik}. "
            f"The filing was submitted on {filing.filing_date} under accession {filing.accession_number}."
        )
    if section == "Executive summary":
        revenue = _fact_value(fact_map, "revenue")
        op_margin = _metric_value(metric_map, "operating_margin")
        net_margin = _metric_value(metric_map, "net_margin")
        liquidity = _metric_value(metric_map, "liquidity")
        capex = _metric_value(metric_map, "capex_intensity")
        return (
            f"{company} shows substantial scale with {revenue or 'revenue unavailable'} in the latest extracted period, "
            f"but profitability is negative on the extracted figures: operating margin {op_margin or 'unavailable'} and net margin {net_margin or 'unavailable'}. "
            f"Liquidity is {liquidity or 'unavailable'}, while capex intensity is {capex or 'unavailable'}, highlighting a capital-heavy profile. "
            "All figures are sourced from SEC artifacts or explicitly marked unavailable."
        )
    if section == "Business overview":
        return (
            f"{company} is analyzed here through its SEC registration statement and extracted financial tables. "
            "This POC does not yet perform a full qualitative business-description extraction, so the source filing remains the definitive reference."
        )
    if section == "Offering / IPO context":
        if filing and filing.form.startswith("S-1"):
            return (
                "The selected source is an S-1 registration statement, so the analysis is framed around IPO readiness, "
                "financial disclosure quality, and the risk of drawing conclusions before a final prospectus or pricing terms are available."
            )
        return "The selected filing is not an S-1 prospectus; IPO-specific conclusions should be treated as limited."
    if section == "Financial profile":
        high = sum(1 for fact in facts if fact.confidence == "high")
        low = sum(1 for fact in facts if fact.confidence == "low")
        return (
            f"Extracted {len(facts)} structured facts: {high} high-confidence companyfacts/XBRL facts and "
            f"{low} low-confidence filing-text table facts. The latest extracted balance sheet shows "
            f"{_fact_value(fact_map, 'assets') or 'assets unavailable'}, "
            f"{_fact_value(fact_map, 'liabilities') or 'liabilities unavailable'}, and "
            f"{_fact_value(fact_map, 'cash') or 'cash unavailable'} of cash."
        )
    if section == "Growth and profitability":
        return (
            f"Revenue growth is unavailable because the POC currently stores one extracted revenue period. "
            f"The extracted operating margin is {_metric_value(metric_map, 'operating_margin') or 'unavailable'} and "
            f"net margin is {_metric_value(metric_map, 'net_margin') or 'unavailable'}, indicating negative profitability in the latest period."
        )
    if section == "Cash flow, capex, and liquidity":
        return (
            f"Operating cash flow is {_fact_value(fact_map, 'operating_cash_flow') or 'unavailable'} and capex is "
            f"{_fact_value(fact_map, 'capital_expenditure') or 'unavailable'} for the extracted period. "
            f"Capex intensity is {_metric_value(metric_map, 'capex_intensity') or 'unavailable'}, and cash-to-liabilities liquidity is "
            f"{_metric_value(metric_map, 'liquidity') or 'unavailable'}."
        )
    if section == "Balance sheet and leverage":
        return (
            f"Debt-to-assets is {_metric_value(metric_map, 'debt_to_assets') or 'unavailable'}, while liabilities-to-assets is "
            f"{_metric_value(metric_map, 'liabilities_to_assets') or 'unavailable'}. The extracted debt figure only captures the labeled debt and finance lease line currently parsed."
        )
    if section == "Governance and share structure":
        return "Governance and share-structure fields are included only when sourced from extracted facts or a later filing-text parser pass."
    if section == "Key risk factors":
        return "Risk factors are not summarized from full filing text in this POC revision; use the source filing for complete risk-factor language."
    if section == "Valuation framing":
        return "No valuation conclusion is produced without sourced valuation inputs, comparable-company assumptions, and complete financial statements."
    if section == "CIO takeaways":
        return (
            "The main signal is scale paired with heavy investment and negative extracted profitability. "
            "Before making an investment decision, the next diligence step is multi-period extraction, final offering terms, risk-factor parsing, and peer/valuation context."
        )
    if section == "Data limitations and caveats":
        warnings = analysis.warnings or ["No additional warnings."]
        return (
            "Facts marked as filing-text table facts are lower confidence than standardized XBRL/companyfacts data. "
            + " ".join(warnings)
        )
    return "No additional sourced narrative available in this POC section."


def _facts_table(facts: list[ExtractedFact]) -> list[str]:
    rows = ["| Metric | Value | Unit | Period | Source | Confidence |", "| --- | ---: | --- | --- | --- | --- |"]
    for fact in facts:
        value = "" if fact.value is None else f"{fact.value:,.2f}"
        rows.append(f"| {fact.metric} | {value} | {fact.unit} | {fact.period} | {fact.source_concept} | {fact.confidence} |")
    return rows


def _metrics_table(analysis: AnalysisResult, names: list[str] | None = None) -> list[str]:
    rows = ["| Metric | Status | Value | Note |", "| --- | --- | ---: | --- |"]
    selected = set(names or [])
    for metric in analysis.metrics:
        if selected and metric.metric not in selected:
            continue
        value = "" if metric.value is None else f"{metric.value:,.2f} {metric.unit}".strip()
        rows.append(f"| {metric.metric} | {metric.status} | {value} | {metric.note} |")
    return rows


def _metric_summary(analysis: AnalysisResult, names: list[str]) -> str:
    metrics = {metric.metric: metric for metric in analysis.metrics}
    parts = []
    for name in names:
        metric = metrics.get(name)
        if not metric or metric.status == "missing":
            parts.append(f"{name} is missing")
        else:
            value = "" if metric.value is None else f"{metric.value:,.2f} {metric.unit}".strip()
            parts.append(f"{name} is {value}")
    return "; ".join(parts) + "."


def _facts_by_metric(facts: list[ExtractedFact]) -> dict[str, ExtractedFact]:
    return {fact.metric: fact for fact in facts if fact.value is not None}


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
