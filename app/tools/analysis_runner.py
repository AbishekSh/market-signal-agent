from __future__ import annotations

from app.schemas import AnalysisMetric, AnalysisResult, ExtractedFact


def run_analysis(facts: list[ExtractedFact]) -> AnalysisResult:
    latest = _latest_by_metric(facts)
    metrics = [
        _ratio("operating_margin", latest, "operating_income", "revenue", "%"),
        _ratio("net_margin", latest, "net_income", "revenue", "%"),
        _ratio("debt_to_assets", latest, "debt", "assets", "x"),
        _ratio("liabilities_to_assets", latest, "liabilities", "assets", "x"),
        _ratio("capex_intensity", latest, "capital_expenditure", "revenue", "%"),
        _cash_burn(latest),
        _liquidity(latest),
        _missing("revenue_growth", "Needs at least two comparable revenue periods; POC extracts latest fact only."),
    ]
    warnings = []
    for name in ["revenue", "operating_income", "net_income", "assets", "liabilities", "cash", "debt"]:
        if name not in latest:
            warnings.append(f"Missing source fact: {name}")
    return AnalysisResult(metrics=metrics, warnings=warnings)


def _latest_by_metric(facts: list[ExtractedFact]) -> dict[str, ExtractedFact]:
    return {fact.metric: fact for fact in facts if fact.value is not None}


def _ratio(metric: str, facts: dict[str, ExtractedFact], numerator: str, denominator: str, unit: str) -> AnalysisMetric:
    num = facts.get(numerator)
    den = facts.get(denominator)
    if not num or not den or den.value in (None, 0):
        return _missing(metric, f"Missing {numerator} or {denominator}.")
    value = (num.value / den.value) * (100 if unit == "%" else 1)
    return AnalysisMetric(metric=metric, value=value, unit=unit, status="computed", note=f"{numerator} / {denominator}")


def _cash_burn(facts: dict[str, ExtractedFact]) -> AnalysisMetric:
    ocf = facts.get("operating_cash_flow")
    if not ocf or ocf.value is None:
        return _missing("cash_burn", "Missing operating cash flow.")
    return AnalysisMetric(
        metric="cash_burn",
        value=abs(min(ocf.value, 0)),
        unit=ocf.unit,
        status="computed",
        note="Positive value indicates operating cash outflow magnitude.",
    )


def _liquidity(facts: dict[str, ExtractedFact]) -> AnalysisMetric:
    cash = facts.get("cash")
    liabilities = facts.get("liabilities")
    if not cash or not liabilities or liabilities.value in (None, 0):
        return _missing("liquidity", "Missing cash or liabilities.")
    return AnalysisMetric(metric="liquidity", value=cash.value / liabilities.value, unit="x", status="computed", note="cash / liabilities")


def _missing(metric: str, note: str) -> AnalysisMetric:
    return AnalysisMetric(metric=metric, status="missing", note=note)
