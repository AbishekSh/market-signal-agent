from app.agent.llm import _normalize_report_sections


def test_report_section_keys_are_normalized() -> None:
    sections = _normalize_report_sections(
        {
            "Executive Summary": "Useful summary",
            "Offering / IPO Context": ["IPO item"],
            "unknown": "ignored",
        }
    )
    assert sections["Executive summary"] == "Useful summary"
    assert sections["Offering / IPO context"] == "- IPO item"
    assert "unknown" not in sections
