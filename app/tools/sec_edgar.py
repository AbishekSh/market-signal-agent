from __future__ import annotations

import time
import re
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.schemas import DownloadResult, FilingMetadata


SEC_TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik_no_zeros}/{accession_no_dashes}/{doc}"

SPACEX_ALIASES = {
    "spacex": ("0001181412", "Space Exploration Technologies Corp."),
    "spacex inc": ("0001181412", "Space Exploration Technologies Corp."),
    "spacex incorporated": ("0001181412", "Space Exploration Technologies Corp."),
    "space exploration technologies": ("0001181412", "Space Exploration Technologies Corp."),
    "space exploration technologies corp": ("0001181412", "Space Exploration Technologies Corp."),
    "space exploration technologies corporation": ("0001181412", "Space Exploration Technologies Corp."),
}


class SECEDGARTool:
    def __init__(self, user_agent: str, min_interval_seconds: float = 0.12, timeout: int = 20):
        self.user_agent = user_agent
        self.min_interval_seconds = min_interval_seconds
        self.timeout = timeout
        self._last_request = 0.0
        self.session = requests.Session()
        retry = Retry(total=3, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504))
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate", "Host": "www.sec.gov"})

    def _get_json(self, url: str) -> dict[str, Any]:
        self._rate_limit()
        headers = dict(self.session.headers)
        if "data.sec.gov" in url:
            headers["Host"] = "data.sec.gov"
        response = self.session.get(url, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _get_text(self, url: str) -> str:
        self._rate_limit()
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def _rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)
        self._last_request = time.monotonic()

    def resolve_company(self, company_name: str) -> tuple[str, str]:
        normalized = _normalize_company_name(company_name)
        if normalized in SPACEX_ALIASES:
            return SPACEX_ALIASES[normalized]
        tickers = self._get_json(SEC_TICKER_URL)
        for row in tickers.values():
            title = str(row.get("title", ""))
            ticker = str(row.get("ticker", ""))
            if normalized in _normalize_company_name(title) or normalized == ticker.lower():
                return f"{int(row['cik_str']):010d}", title
        raise ValueError(f"Could not resolve company from SEC tickers: {company_name}")

    def get_submissions(self, cik: str) -> dict[str, Any]:
        return self._get_json(SEC_SUBMISSIONS_URL.format(cik=cik.zfill(10)))

    def find_filing(self, cik: str, company_name: str, forms: list[str]) -> FilingMetadata:
        submissions = self.get_submissions(cik)
        recent = submissions.get("filings", {}).get("recent", {})
        accession_numbers = recent.get("accessionNumber", [])
        form_values = recent.get("form", [])
        filing_dates = recent.get("filingDate", [])
        primary_docs = recent.get("primaryDocument", [])
        for wanted in forms:
            for i, form in enumerate(form_values):
                if form == wanted or (wanted.startswith("424B") and form.startswith("424B")):
                    accession = accession_numbers[i]
                    primary_doc = primary_docs[i] if i < len(primary_docs) else ""
                    filing_url = SEC_ARCHIVES_URL.format(
                        cik_no_zeros=str(int(cik)),
                        accession_no_dashes=accession.replace("-", ""),
                        doc=primary_doc,
                    )
                    return FilingMetadata(
                        cik=cik.zfill(10),
                        company_name=company_name,
                        form=form,
                        accession_number=accession,
                        filing_date=filing_dates[i] if i < len(filing_dates) else "",
                        primary_document=primary_doc,
                        filing_url=filing_url,
                        selected_differs_from_requested=form != forms[0],
                    )
        raise ValueError(f"No filing found for forms: {', '.join(forms)}")

    def download_artifacts(self, metadata: FilingMetadata, run_dir: Path) -> DownloadResult:
        run_dir.mkdir(parents=True, exist_ok=True)
        files: dict[str, Path] = {}
        warnings: list[str] = []
        filing_text = ""
        companyfacts = None

        if metadata.filing_url:
            try:
                filing_text = self._get_text(metadata.filing_url)
                filing_path = run_dir / f"{metadata.accession_number.replace('-', '')}-{metadata.primary_document or 'filing.html'}"
                filing_path.write_text(filing_text, encoding="utf-8")
                files["filing"] = filing_path
            except Exception as exc:
                warnings.append(f"Could not download filing document: {exc}")

        try:
            companyfacts = self._get_json(SEC_COMPANYFACTS_URL.format(cik=metadata.cik.zfill(10)))
            facts_path = run_dir / "companyfacts.json"
            facts_path.write_text(__import__("json").dumps(companyfacts, indent=2), encoding="utf-8")
            files["companyfacts"] = facts_path
        except Exception as exc:
            warnings.append(f"Companyfacts unavailable: {exc}")

        return DownloadResult(metadata=metadata, files=files, companyfacts=companyfacts, filing_text=filing_text, warnings=warnings)

    def fetch_for_company(self, company_name: str, filing_type: str, run_dir: Path) -> DownloadResult:
        cik, formal_name = self.resolve_company(company_name)
        forms = [filing_type]
        if filing_type == "S-1":
            forms.extend(["S-1/A", "424B", "424B4", "10-K", "10-Q"])
        metadata = self.find_filing(cik, formal_name, forms)
        return self.download_artifacts(metadata, run_dir)


def _normalize_company_name(company_name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", company_name.lower()).strip()
    return re.sub(r"\s+", " ", normalized)
