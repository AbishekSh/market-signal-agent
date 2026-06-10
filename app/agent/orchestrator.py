from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.agent.llm import LLMClient
from app.config import Settings
from app.reports.report_writer import build_report, save_report
from app.schemas import EmailStatus, ResearchResponse, TelegramStatus
from app.storage.audit_log import append_audit_event
from app.tools.analysis_runner import run_analysis
from app.tools.emailer import send_report_if_configured
from app.tools.sec_edgar import SECEDGARTool
from app.tools.telegram import build_telegram_summary, send_telegram_summary
from app.tools.xbrl_parser import parse_companyfacts, parse_filing_text_fallback


class ResearchOrchestrator:
    def __init__(self, settings: Settings, llm: LLMClient, sec_tool: SECEDGARTool):
        self.settings = settings
        self.llm = llm
        self.sec_tool = sec_tool

    def run(self, message: str, telegram_chat_id: str | None = None) -> ResearchResponse:
        run_id = uuid.uuid4().hex
        created_at = datetime.now(timezone.utc)
        run_dir = self.settings.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        warnings: list[str] = []
        errors: list[str] = []
        report_markdown = ""
        report_path = ""
        filing = None
        downloaded_files: list[str] = []

        intent = self.llm.parse_intent(message)
        facts = []
        analysis = run_analysis([])
        email_status = EmailStatus(status="skipped", detail="Report was not generated.")
        telegram_status = TelegramStatus(status="skipped", detail="Telegram is optional for the web milestone.")

        try:
            download = self.sec_tool.fetch_for_company(intent.company_name, intent.target_filing_type, run_dir)
            filing = download.metadata
            warnings.extend(download.warnings)
            downloaded_files = [str(path) for path in download.files.values()]
            facts = parse_companyfacts(download.companyfacts)
            if not facts:
                facts = parse_filing_text_fallback(download.filing_text)
                if facts:
                    warnings.append("Used low-confidence filing text fallback facts.")
            analysis = run_analysis(facts)
            warnings.extend(analysis.warnings)
            if filing.selected_differs_from_requested:
                warnings.append(f"Selected {filing.form} because requested {intent.target_filing_type} was unavailable.")
        except Exception as exc:
            errors.append(str(exc))
            warnings.extend(analysis.warnings)

        narrative = self.llm.generate_report_sections(intent, filing, [fact.model_dump() for fact in facts], analysis)
        report_markdown = build_report(intent, filing, facts, analysis, narrative)
        path = save_report(self.settings.reports_dir, run_id, report_markdown)
        report_path = str(path)
        email_status = send_report_if_configured(self.settings, f"{intent.company_name} research report", report_markdown)
        if telegram_chat_id:
            telegram_summary = build_telegram_summary(
                intent=intent,
                filing=filing,
                facts=facts,
                analysis=analysis,
                warnings=warnings,
                errors=errors,
                report_name=path.name,
            )
            telegram_status = send_telegram_summary(self.settings.telegram_bot_token, telegram_chat_id, telegram_summary)

        response = ResearchResponse(
            ok=not errors,
            run_id=run_id,
            created_at=created_at,
            parsed_intent=intent,
            filing_metadata=filing,
            report_path=report_path,
            report_markdown=report_markdown,
            email_status=email_status,
            telegram_status=telegram_status,
            warnings=warnings,
            errors=errors,
        )
        append_audit_event(
            self.settings.audit_dir,
            {
                "run_id": run_id,
                "original_message": message,
                "parsed_intent": intent.model_dump(),
                "sec_company_cik": filing.cik if filing else "",
                "sec_company_name": filing.company_name if filing else "",
                "filing_accession_number": filing.accession_number if filing else "",
                "downloaded_files": downloaded_files,
                "report_path": report_path,
                "email_status": email_status.model_dump(),
                "telegram_status": telegram_status.model_dump(),
                "warnings": warnings,
                "errors": errors,
            },
        )
        return response


def safe_report_path(reports_dir: Path, report_name: str) -> Path:
    candidate = (reports_dir / report_name).resolve()
    base = reports_dir.resolve()
    if base not in candidate.parents or candidate.suffix != ".md":
        raise ValueError("Invalid report path")
    return candidate
