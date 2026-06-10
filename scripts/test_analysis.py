from app.schemas import ExtractedFact
from app.tools.analysis_runner import run_analysis


def main() -> None:
    facts = [
        ExtractedFact(metric="revenue", source_concept="demo", value=100.0, unit="USD"),
        ExtractedFact(metric="operating_income", source_concept="demo", value=18.0, unit="USD"),
        ExtractedFact(metric="net_income", source_concept="demo", value=9.0, unit="USD"),
        ExtractedFact(metric="assets", source_concept="demo", value=200.0, unit="USD"),
        ExtractedFact(metric="liabilities", source_concept="demo", value=80.0, unit="USD"),
        ExtractedFact(metric="cash", source_concept="demo", value=30.0, unit="USD"),
        ExtractedFact(metric="debt", source_concept="demo", value=20.0, unit="USD"),
    ]
    analysis = run_analysis(facts)
    for metric in analysis.metrics:
        print(f"{metric.metric}: {metric.status} {metric.value} {metric.unit} {metric.note}")
    if analysis.warnings:
        print("Warnings:")
        for warning in analysis.warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
