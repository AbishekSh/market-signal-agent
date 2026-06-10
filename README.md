# Market Signal Agent

A working POC for a constrained, web-first financial research agent. The first milestone is intentionally simple: open `http://localhost:8000`, enter a research request, run the workflow, and view a generated Markdown report in the page.

The default sample request is:

```text
Analyze SpaceX prospectus ahead of the IPO
```

## What It Does

- Parses the request into structured intent.
- The LLM interprets what company the user likely means, but the final company identity and CIK are resolved through deterministic code and SEC EDGAR data.
- Searches SEC EDGAR for the requested filing type with IPO-oriented fallbacks.
- Downloads SEC filing artifacts and companyfacts when available.
- Extracts structured XBRL/companyfacts data where possible.
- Runs deterministic Python analysis for margins, leverage, liquidity, capex intensity, cash burn, and missing-data warnings.
- Generates and saves a hedge-fund-CIO-style Markdown report.
- Skips Gmail SMTP unless complete non-placeholder credentials are configured.
- Keeps Telegram as an optional later webhook, not the primary interface.

## Run Locally With Docker

Install and start Ollama on your Mac, then pull the default model:

```bash
ollama pull llama3.2:3b
curl http://localhost:11434/api/tags
```

Create your environment file:

```bash
cp .env.example .env
```

Set `SEC_USER_AGENT` in `.env` to a real contact value such as:

```text
SEC_USER_AGENT=Your Name your.email@example.com
```

Start the app:

```bash
docker compose up --build
```

Open:

```text
http://localhost:8000
```

Docker Desktop for Mac reaches Mac-hosted Ollama through:

```text
OLLAMA_HOST=http://host.docker.internal:11434
```

If Docker can resolve `host.docker.internal` but gets connection refused, restart Ollama so it listens beyond localhost:

```bash
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

## API

Health:

```bash
curl http://localhost:8000/health
```

Run research:

```bash
curl -X POST http://localhost:8000/web/research \
  -H 'Content-Type: application/json' \
  -d '{"message":"Analyze SpaceX prospectus ahead of the IPO"}'
```

Read a saved report:

```bash
curl http://localhost:8000/reports/<report-name>.md
```

Telegram placeholder:

```text
POST /telegram/webhook
```

Telegram is optional. If `TELEGRAM_BOT_TOKEN` is absent, Telegram sending is skipped.

## Scripts

```bash
python scripts/test_sec_lookup.py
python scripts/test_analysis.py
python scripts/test_ollama.py
```

Inside Docker:

```bash
docker compose run --rm financial-agent pytest
```

## Gmail SMTP

Email is skipped unless all SMTP fields are complete and not placeholder values.

For Gmail, use a Google App Password:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your.email@gmail.com
SMTP_PASSWORD=your_google_app_password
SMTP_FROM=your.email@gmail.com
REPORT_EMAIL_TO=recipient@example.com
```

Do not use your normal Gmail password.

## Files

```text
app/main.py                  FastAPI app and browser UI
app/agent/                   Orchestrator, prompts, Ollama/fallback LLMs
app/tools/sec_edgar.py       Typed SEC EDGAR client
app/tools/xbrl_parser.py     Companyfacts and conservative filing text extraction
app/tools/analysis_runner.py Deterministic calculations
app/reports/report_writer.py Markdown report writer
app/storage/audit_log.py     JSONL workflow audit log
workspace/reports/           Saved reports
workspace/audit/runs.jsonl   Audit events
```

## Ubuntu VPS Notes

For a VPS, Ollama may run on the same host or a separate service. You may need a Linux-specific Compose override using `host-gateway`, or you can set `OLLAMA_HOST` to a reachable private network URL. Do not add an Ollama service to this first Mac-focused compose file unless you intentionally change the deployment model.

## Security And Limitations

- The LLM cannot run shell commands.
- User messages flow through typed tools only.
- Numerical analysis is deterministic Python and missing values are marked missing.
- Reports are research aids, not investment advice.
- SEC extraction is conservative and may miss values in complex filings.
- The fallback LLM keeps the workflow running when Ollama is unavailable, but generated narrative is intentionally limited.
- Audit logs avoid secrets but do include request text, parsed intent, filing metadata, report paths, warnings, and errors.
