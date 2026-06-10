from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    message: str = Field(..., min_length=3)


class Intent(BaseModel):
    company_name: str
    likely_formal_company_name: str = ""
    target_filing_type: str = "S-1"
    analysis_objective: str = "Assess IPO prospectus and investment implications"
    target_audience: str = "hedge fund CIO"


class FilingMetadata(BaseModel):
    cik: str
    company_name: str
    form: str = ""
    accession_number: str = ""
    filing_date: str = ""
    primary_document: str = ""
    filing_url: str = ""
    selected_differs_from_requested: bool = False


class ExtractedFact(BaseModel):
    metric: str
    source_concept: str
    value: float | None = None
    unit: str = ""
    period: str = ""
    confidence: str = "low"


class AnalysisMetric(BaseModel):
    metric: str
    value: float | None = None
    unit: str = ""
    status: str = "missing"
    note: str = ""


class AnalysisResult(BaseModel):
    metrics: list[AnalysisMetric]
    warnings: list[str] = []


class EmailStatus(BaseModel):
    status: str
    detail: str = ""


class TelegramStatus(BaseModel):
    status: str
    detail: str = ""


class ResearchResponse(BaseModel):
    ok: bool
    run_id: str
    created_at: datetime
    parsed_intent: Intent
    filing_metadata: FilingMetadata | None = None
    report_path: str = ""
    report_markdown: str = ""
    email_status: EmailStatus
    telegram_status: TelegramStatus
    warnings: list[str] = []
    errors: list[str] = []


class DownloadResult(BaseModel):
    metadata: FilingMetadata
    files: dict[str, Path] = {}
    companyfacts: dict[str, Any] | None = None
    filing_text: str = ""
    warnings: list[str] = []
