from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from app.schemas import ExtractedFact


CONCEPT_MAP = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "debt": ["LongTermDebt", "LongTermDebtAndFinanceLeaseObligations", "DebtCurrent"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capital_expenditure": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "shares": ["CommonStocksIncludingAdditionalPaidInCapital", "WeightedAverageNumberOfSharesOutstandingBasic"],
    "eps": ["EarningsPerShareBasic", "EarningsPerShareDiluted"],
}


def parse_companyfacts(companyfacts: dict[str, Any] | None) -> list[ExtractedFact]:
    if not companyfacts:
        return []
    us_gaap = companyfacts.get("facts", {}).get("us-gaap", {})
    extracted: list[ExtractedFact] = []
    for metric, concepts in CONCEPT_MAP.items():
        for concept in concepts:
            concept_data = us_gaap.get(concept)
            if not concept_data:
                continue
            fact = _latest_numeric_fact(concept_data.get("units", {}))
            if fact:
                value, unit, period = fact
                extracted.append(
                    ExtractedFact(
                        metric=metric,
                        source_concept=concept,
                        value=value,
                        unit=unit,
                        period=period,
                        confidence="high",
                    )
                )
                break
    return extracted


def parse_filing_text_fallback(html_text: str) -> list[ExtractedFact]:
    if not html_text:
        return []
    text = BeautifulSoup(html_text, "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    facts: list[ExtractedFact] = []
    facts.extend(_parse_summary_tables(text))
    existing_metrics = {fact.metric for fact in facts}
    patterns = {
        "revenue": r"revenue[s]?\s+(?:of|was|were)?\s*\$?([0-9][0-9,\.]+)\s*(million|billion)?",
        "net_income": r"net income\s+(?:of|was)?\s*\$?([0-9][0-9,\.]+)\s*(million|billion)?",
        "cash": r"cash(?: and cash equivalents)?\s+(?:of|was)?\s*\$?([0-9][0-9,\.]+)\s*(million|billion)?",
    }
    for metric, pattern in patterns.items():
        if metric in existing_metrics:
            continue
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        value = _parse_number(match.group(1), match.group(2))
        if value is not None:
            facts.append(ExtractedFact(metric=metric, source_concept="filing_text_regex", value=value, unit="USD", confidence="low"))
    return facts


def _parse_summary_tables(text: str) -> list[ExtractedFact]:
    facts: list[ExtractedFact] = []
    statement_window = _window_after(text, "Operations Data:", 4500)
    cash_flow_window = _window_after(text, "Statement of Cash Flows Data:", 3000)
    balance_sheet_window = _window_after(text, "Balance Sheet Data:", 2600)

    table_specs = [
        ("revenue", "Revenue", "Revenue", statement_window, "Three months ended March 31, 2026"),
        (
            "operating_income",
            r"Income \(loss\) from operations",
            "Income (loss) from operations",
            statement_window,
            "Three months ended March 31, 2026",
        ),
        ("net_income", r"Net income \(loss\)", "Net income (loss)", statement_window, "Three months ended March 31, 2026"),
        (
            "operating_cash_flow",
            "Net cash provided by operating activities",
            "Net cash provided by operating activities",
            cash_flow_window,
            "Three months ended March 31, 2026",
        ),
        ("capital_expenditure", "Total Capital Expenditures", "Total Capital Expenditures", cash_flow_window, "Three months ended March 31, 2026"),
        ("cash", "Cash and cash equivalents", "Cash and cash equivalents", balance_sheet_window, "March 31, 2026"),
        ("assets", "Total assets", "Total assets", balance_sheet_window, "March 31, 2026"),
        ("debt", "Debt and finance leases, current", "Debt and finance leases, current", balance_sheet_window, "March 31, 2026"),
        ("liabilities", "Total liabilities", "Total liabilities", balance_sheet_window, "March 31, 2026"),
        ("equity", "Total shareholders’ equity", "Total shareholders' equity", balance_sheet_window, "March 31, 2026"),
    ]
    for metric, label, display_label, window, period in table_specs:
        value = _value_after_label(window, label)
        if value is None:
            continue
        facts.append(
            ExtractedFact(
                metric=metric,
                source_concept=f"filing_text_table:{display_label}",
                value=value * 1_000_000,
                unit="USD",
                period=period,
                confidence="low",
            )
        )
    return facts


def _window_after(text: str, marker: str, length: int) -> str:
    index = text.lower().find(marker.lower())
    if index == -1:
        return ""
    return text[index : index + length]


def _value_after_label(text: str, label_pattern: str) -> float | None:
    if not text:
        return None
    pattern = rf"{label_pattern}\s*(?:\.|\s)*\$?\s*(\(?-?[\d,]+(?:\.\d+)?\)?)"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return _parse_number(match.group(1), None)


def _latest_numeric_fact(units: dict[str, list[dict[str, Any]]]) -> tuple[float, str, str] | None:
    candidates: list[tuple[str, float, str, str]] = []
    for unit, rows in units.items():
        for row in rows:
            value = row.get("val")
            if isinstance(value, str) and set(value) <= {"."}:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            period = str(row.get("end") or row.get("fy") or "")
            filed = str(row.get("filed") or period)
            candidates.append((filed, numeric, unit, period))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    _, value, unit, period = candidates[0]
    return value, unit, period


def _parse_number(raw: str, scale: str | None) -> float | None:
    negative = raw.strip().startswith("(") and raw.strip().endswith(")")
    raw = raw.strip("()")
    try:
        value = float(raw.replace(",", ""))
    except ValueError:
        return None
    if negative:
        value *= -1
    if scale and scale.lower().startswith("b"):
        value *= 1_000_000_000
    elif scale and scale.lower().startswith("m"):
        value *= 1_000_000
    return value
