from app.tools.xbrl_parser import parse_filing_text_fallback


def test_filing_text_summary_tables_are_extracted() -> None:
    html = """
    <html><body>
    Stat ements of Operations Data:
    Three Months Ended March 31, 2026 2025 (in millions)
    Revenue ............................................. $ 4,694 $ 4,067
    Total costs and expenses ........... 6,637 4,040
    Income (loss) from operations ........... (1,943) 27
    Net income (loss) .............................. $ (4,276) $ (528)
    Statement of Cash Flows Data:
    Net cash provided by operating activities .......................................... $ 1,047 $ 727
    Total Capital Expenditures ................. $ 10,107 $ 4,140
    Balance Sheet Data:
    March 31, 2026 2025 (in millions)
    Cash and cash equivalents .............................................................. $ 15,852 $ 24,747
    Total assets .................................................................................... 102,094 92,079
    Debt and finance leases, current .................................................... 1,538 928
    Total liabilities ................................................................................ 60,512 50,754
    Total shareholders’ equity ............................................................. 34,533 2,573
    </body></html>
    """
    facts = {fact.metric: fact for fact in parse_filing_text_fallback(html)}
    assert facts["revenue"].value == 4_694_000_000
    assert facts["operating_income"].value == -1_943_000_000
    assert facts["net_income"].value == -4_276_000_000
    assert facts["operating_cash_flow"].value == 1_047_000_000
    assert facts["capital_expenditure"].value == 10_107_000_000
    assert facts["assets"].value == 102_094_000_000
    assert facts["liabilities"].value == 60_512_000_000
