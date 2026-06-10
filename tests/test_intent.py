from app.agent.llm import SafeFallbackLLM


def test_spacex_ipo_intent_fallback() -> None:
    intent = SafeFallbackLLM().parse_intent("Analyze SpaceX prospectus ahead of the IPO")
    assert intent.company_name == "SpaceX"
    assert intent.likely_formal_company_name == "Space Exploration Technologies Corp."
    assert intent.target_filing_type == "S-1"
    assert intent.target_audience == "hedge fund CIO"
