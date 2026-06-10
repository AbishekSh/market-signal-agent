from app.reports.report_writer import build_report
from app.schemas import AnalysisMetric, AnalysisResult, ExtractedFact, FilingMetadata, Intent


def test_deterministic_report_fallback_is_interpretive_not_placeholder() -> None:
    intent = Intent(company_name="SpaceX", target_audience="hedge fund CIO")
    filing = FilingMetadata(
        cik="0001181412",
        company_name="Space Exploration Technologies Corp.",
        form="S-1",
        accession_number="0000000000-00-000000",
        filing_date="2026-05-20",
    )
    facts = [
        ExtractedFact(metric="revenue", source_concept="demo", value=4_694_000_000, unit="USD", confidence="low"),
        ExtractedFact(metric="assets", source_concept="demo", value=102_094_000_000, unit="USD", confidence="low"),
        ExtractedFact(metric="liabilities", source_concept="demo", value=60_512_000_000, unit="USD", confidence="low"),
        ExtractedFact(metric="cash", source_concept="demo", value=15_852_000_000, unit="USD", confidence="low"),
    ]
    analysis = AnalysisResult(
        metrics=[
            AnalysisMetric(metric="operating_margin", value=-41.39, unit="%", status="computed"),
            AnalysisMetric(metric="net_margin", value=-91.10, unit="%", status="computed"),
            AnalysisMetric(metric="liquidity", value=0.26, unit="x", status="computed"),
            AnalysisMetric(metric="capex_intensity", value=215.32, unit="%", status="computed"),
        ]
    )
    report = build_report(intent, filing, facts, analysis, {})
    assert "Narrative generation used the safe fallback" not in report
    assert "No additional sourced narrative available" not in report
    assert "substantial scale" in report
    assert report.count("| operating_margin |") == 1
