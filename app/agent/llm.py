from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

import requests

from app.agent.prompts import INTENT_SYSTEM_PROMPT, REPORT_SYSTEM_PROMPT
from app.reports.report_writer import REPORT_SECTIONS
from app.schemas import AnalysisResult, FilingMetadata, Intent


class LLMClient(ABC):
    @abstractmethod
    def parse_intent(self, message: str) -> Intent:
        raise NotImplementedError

    @abstractmethod
    def generate_report_sections(
        self,
        intent: Intent,
        filing: FilingMetadata | None,
        facts: list[dict[str, Any]],
        analysis: AnalysisResult,
    ) -> dict[str, str]:
        raise NotImplementedError


class SafeFallbackLLM(LLMClient):
    def parse_intent(self, message: str) -> Intent:
        lower = message.lower()
        company = "SpaceX" if "spacex" in lower or "space exploration" in lower else message.strip()
        filing = "S-1" if "ipo" in lower or "prospectus" in lower else "10-K"
        formal = "Space Exploration Technologies Corp." if company == "SpaceX" else company
        return Intent(
            company_name=company,
            likely_formal_company_name=formal,
            target_filing_type=filing,
            analysis_objective="Analyze prospectus ahead of IPO" if filing == "S-1" else "Analyze filing",
            target_audience="hedge fund CIO",
        )

    def generate_report_sections(
        self,
        intent: Intent,
        filing: FilingMetadata | None,
        facts: list[dict[str, Any]],
        analysis: AnalysisResult,
    ) -> dict[str, str]:
        return {}


class OllamaClient(LLMClient):
    def __init__(self, host: str, model: str, timeout: int = 60):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.fallback = SafeFallbackLLM()

    def _generate(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": f"{system_prompt}\n\n{user_prompt}",
            "stream": False,
        }
        if "JSON" in system_prompt:
            payload["format"] = "json"
        response = requests.post(
            f"{self.host}/api/generate",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json().get("response", "")

    def parse_intent(self, message: str) -> Intent:
        try:
            raw = self._generate(INTENT_SYSTEM_PROMPT, message)
            data = json.loads(raw)
            return Intent(**data)
        except Exception:
            return self.fallback.parse_intent(message)

    def generate_report_sections(
        self,
        intent: Intent,
        filing: FilingMetadata | None,
        facts: list[dict[str, Any]],
        analysis: AnalysisResult,
    ) -> dict[str, str]:
        payload = {
            "intent": intent.model_dump(),
            "filing": filing.model_dump() if filing else None,
            "facts": facts[:40],
            "analysis": analysis.model_dump(),
        }
        try:
            raw = self._generate(REPORT_SYSTEM_PROMPT, json.dumps(payload, default=str))
            data = json.loads(raw)
            if isinstance(data, dict):
                merged = self.fallback.generate_report_sections(intent, filing, facts, analysis)
                merged.update(_normalize_report_sections(data))
                return merged
        except Exception:
            pass
        return self.fallback.generate_report_sections(intent, filing, facts, analysis)


def _metric_sentence(analysis: AnalysisResult, names: list[str]) -> str:
    parts = []
    by_name = {m.metric: m for m in analysis.metrics}
    for name in names:
        metric = by_name.get(name)
        if not metric or metric.status == "missing":
            parts.append(f"{name}: missing")
        else:
            suffix = f" {metric.unit}" if metric.unit else ""
            parts.append(f"{name}: {metric.value:.2f}{suffix}" if metric.value is not None else f"{name}: unavailable")
    return "; ".join(parts) + "."


def _normalize_report_sections(data: dict[str, Any]) -> dict[str, str]:
    canonical = {_section_key(section): section for section in REPORT_SECTIONS}
    normalized: dict[str, str] = {}
    for key, value in data.items():
        section = canonical.get(_section_key(str(key)))
        if not section:
            continue
        text = _stringify_section(value).strip()
        if text:
            normalized[section] = text
    return normalized


def _section_key(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())


def _stringify_section(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(f"- {_stringify_section(item)}" for item in value)
    if isinstance(value, dict):
        return "\n".join(f"- {key}: {_stringify_section(item)}" for key, item in value.items())
    return str(value)
