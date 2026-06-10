from app.schemas import AnalysisMetric, AnalysisResult, ExtractedFact, FilingMetadata, Intent
from app.tools.telegram import build_telegram_summary, normalize_message_text


def test_normalize_start_command_with_research_text() -> None:
    assert normalize_message_text("/start Analyze SpaceX prospectus ahead of the IPO") == "Analyze SpaceX prospectus ahead of the IPO"


def test_normalize_start_command_without_text_uses_default() -> None:
    assert normalize_message_text("/start") == "Analyze SpaceX prospectus ahead of the IPO"


def test_telegram_summary_is_concise_and_not_full_markdown() -> None:
    summary = build_telegram_summary(
        intent=Intent(company_name="SpaceX"),
        filing=FilingMetadata(
            cik="0001181412",
            company_name="Space Exploration Technologies Corp.",
            form="S-1",
            accession_number="0000000000-00-000000",
            filing_date="2026-05-20",
        ),
        facts=[
            ExtractedFact(metric="revenue", source_concept="demo", value=4_694_000_000, unit="USD"),
            ExtractedFact(metric="cash", source_concept="demo", value=15_852_000_000, unit="USD"),
        ],
        analysis=AnalysisResult(
            metrics=[
                AnalysisMetric(metric="operating_margin", value=-41.39, unit="%", status="computed"),
                AnalysisMetric(metric="net_margin", value=-91.10, unit="%", status="computed"),
                AnalysisMetric(metric="liquidity", value=0.26, unit="x", status="computed"),
                AnalysisMetric(metric="capex_intensity", value=215.32, unit="%", status="computed"),
            ]
        ),
        warnings=["Used low-confidence filing text fallback facts."],
        errors=[],
        report_name="abc.md",
    )
    assert "research summary" in summary
    assert "Operating margin: -41.39 %" in summary
    assert "# " not in summary
    assert len(summary) < 1200
