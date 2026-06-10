from app.tools.sec_edgar import SECEDGARTool


def test_spacex_inc_alias_resolves_without_sec_ticker_lookup() -> None:
    tool = SECEDGARTool(user_agent="Test test@example.com")
    cik, name = tool.resolve_company("SpaceX, Inc.")
    assert cik == "0001181412"
    assert name == "Space Exploration Technologies Corp."
