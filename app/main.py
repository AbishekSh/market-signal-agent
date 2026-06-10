from __future__ import annotations

from html import escape

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse

from app.agent.llm import OllamaClient
from app.agent.orchestrator import ResearchOrchestrator, safe_report_path
from app.config import get_settings
from app.schemas import ResearchRequest
from app.tools.sec_edgar import SECEDGARTool
from app.tools.telegram import extract_message

app = FastAPI(title="Financial Research Agent POC")


def _orchestrator() -> ResearchOrchestrator:
    settings = get_settings()
    return ResearchOrchestrator(
        settings=settings,
        llm=OllamaClient(settings.ollama_host, settings.ollama_model),
        sec_tool=SECEDGARTool(settings.sec_user_agent),
    )


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return HTML_PAGE


@app.get("/health")
def health() -> dict:
    settings = get_settings()
    warnings = []
    ollama_status = "unknown"
    try:
        response = requests.get(f"{settings.ollama_host.rstrip('/')}/api/tags", timeout=3)
        ollama_status = "ok" if response.ok else f"http_{response.status_code}"
    except Exception as exc:
        ollama_status = "unreachable"
        warnings.append(f"Ollama unavailable: {exc}")
    if not settings.sec_user_agent_configured():
        warnings.append("SEC_USER_AGENT is a placeholder; set a compliant contact value.")
    if not settings.smtp_configured():
        warnings.append("SMTP is not configured; report email will be skipped.")
    return {
        "status": "ok",
        "ollama_host": settings.ollama_host,
        "ollama_model": settings.ollama_model,
        "ollama_status": ollama_status,
        "warnings": warnings,
    }


@app.post("/web/research")
def web_research(request: ResearchRequest) -> dict:
    return _orchestrator().run(request.message).model_dump(mode="json")


@app.get("/reports/{report_name}", response_class=PlainTextResponse)
def get_report(report_name: str) -> str:
    settings = get_settings()
    try:
        path = safe_report_path(settings.reports_dir, report_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return path.read_text(encoding="utf-8")


@app.post("/telegram/webhook")
def telegram_webhook(update: dict) -> dict:
    chat_id, text = extract_message(update)
    if not text:
        return {"ok": False, "error": "No Telegram message text found"}
    return _orchestrator().run(text, telegram_chat_id=chat_id).model_dump(mode="json")


HTML_PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Financial Research Agent</title>
  <style>
    :root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; background: #f7f8fa; color: #1d252f; }
    main { max-width: 1120px; margin: 0 auto; padding: 32px 20px 48px; }
    h1 { font-size: 28px; margin: 0 0 16px; letter-spacing: 0; }
    .layout { display: grid; grid-template-columns: minmax(280px, 420px) 1fr; gap: 20px; align-items: start; }
    .panel { background: white; border: 1px solid #d9dee7; border-radius: 8px; padding: 18px; }
    label { display: block; font-weight: 650; margin-bottom: 8px; }
    textarea { box-sizing: border-box; width: 100%; min-height: 170px; resize: vertical; border: 1px solid #bbc4d1; border-radius: 6px; padding: 12px; font: inherit; }
    button { margin-top: 12px; width: 100%; border: 0; border-radius: 6px; background: #1f6feb; color: white; padding: 12px 14px; font-weight: 700; cursor: pointer; }
    button:disabled { background: #8895a7; cursor: wait; }
    .status { font-size: 14px; color: #536173; white-space: pre-wrap; }
    .meta { display: grid; gap: 8px; font-size: 14px; color: #334155; margin-bottom: 16px; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #0f172a; color: #e5edf8; padding: 16px; border-radius: 8px; min-height: 420px; }
    .error { color: #a40019; font-weight: 650; }
    @media (max-width: 820px) { .layout { grid-template-columns: 1fr; } main { padding-top: 20px; } }
  </style>
</head>
<body>
<main>
  <h1>Financial Research Agent</h1>
  <div class="layout">
    <section class="panel">
      <label for="message">Research request</label>
      <textarea id="message">Analyze SpaceX prospectus ahead of the IPO</textarea>
      <button id="run">Run research workflow</button>
      <p id="health" class="status">Checking readiness...</p>
      <p id="error" class="error"></p>
    </section>
    <section class="panel">
      <div id="meta" class="meta"></div>
      <pre id="report">Run a workflow to generate a Markdown report.</pre>
    </section>
  </div>
</main>
<script>
const healthEl = document.getElementById("health");
const errorEl = document.getElementById("error");
const metaEl = document.getElementById("meta");
const reportEl = document.getElementById("report");
const runBtn = document.getElementById("run");

async function loadHealth() {
  const res = await fetch("/health");
  const data = await res.json();
  healthEl.textContent = `Service: ${data.status}\\nOllama: ${data.ollama_status} (${data.ollama_host})\\n${(data.warnings || []).join("\\n")}`;
}

runBtn.addEventListener("click", async () => {
  runBtn.disabled = true;
  errorEl.textContent = "";
  metaEl.textContent = "";
  reportEl.textContent = "Running workflow...";
  try {
    const res = await fetch("/web/research", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: document.getElementById("message").value})
    });
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data));
    metaEl.innerHTML = `
      <div><strong>Run:</strong> ${escapeHtml(data.run_id)}</div>
      <div><strong>Company:</strong> ${escapeHtml(data.parsed_intent.company_name)}</div>
      <div><strong>Filing:</strong> ${escapeHtml(data.filing_metadata?.form || "Unavailable")}</div>
      <div><strong>Email:</strong> ${escapeHtml(data.email_status.status)}</div>
      <div><strong>Warnings:</strong> ${escapeHtml((data.warnings || []).join("; ") || "None")}</div>
    `;
    reportEl.textContent = data.report_markdown || "No report returned.";
    if (data.errors && data.errors.length) errorEl.textContent = data.errors.join("; ");
  } catch (err) {
    errorEl.textContent = String(err);
    reportEl.textContent = "Workflow failed.";
  } finally {
    runBtn.disabled = false;
  }
});

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}

loadHealth().catch(err => { healthEl.textContent = String(err); });
</script>
</body>
</html>
"""
