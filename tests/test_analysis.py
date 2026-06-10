from app.schemas import ExtractedFact
from app.tools.analysis_runner import run_analysis


def test_analysis_computes_deterministic_ratios() -> None:
    facts = [
        ExtractedFact(metric="revenue", source_concept="demo", value=100.0, unit="USD"),
        ExtractedFact(metric="operating_income", source_concept="demo", value=20.0, unit="USD"),
        ExtractedFact(metric="net_income", source_concept="demo", value=10.0, unit="USD"),
        ExtractedFact(metric="assets", source_concept="demo", value=200.0, unit="USD"),
        ExtractedFact(metric="liabilities", source_concept="demo", value=50.0, unit="USD"),
        ExtractedFact(metric="cash", source_concept="demo", value=25.0, unit="USD"),
        ExtractedFact(metric="debt", source_concept="demo", value=40.0, unit="USD"),
        ExtractedFact(metric="capital_expenditure", source_concept="demo", value=15.0, unit="USD"),
    ]
    result = run_analysis(facts)
    metrics = {metric.metric: metric for metric in result.metrics}
    assert metrics["operating_margin"].value == 20.0
    assert metrics["net_margin"].value == 10.0
    assert metrics["debt_to_assets"].value == 0.2
    assert metrics["liquidity"].value == 0.5
    assert metrics["capex_intensity"].value == 15.0


def test_analysis_marks_missing_values() -> None:
    result = run_analysis([])
    assert all(metric.status == "missing" for metric in result.metrics)
    assert "Missing source fact: revenue" in result.warnings
