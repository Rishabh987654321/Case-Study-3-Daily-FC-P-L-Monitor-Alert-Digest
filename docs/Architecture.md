# Architecture — Daily FC P&L Monitor & Alert Digest

## System Overview

An agentic pipeline that ingests daily FC financial data, computes P&L metrics, detects anomalies against configurable thresholds, generates plain-language insights, and delivers color-coded digests.

## Agent Pipeline

The system is decomposed into five specialized agents, each with a clear input/output contract:

```
CSV/Excel Upload
      │
      ▼
┌─────────────────┐
│  Ingest Agent    │  Parse, validate, normalize tabular data
└────────┬────────┘
         │  List[FCDayRecord]
         ▼
┌─────────────────┐
│  Compute Agent   │  CM1, CM2, %-of-revenue for each cost line
└────────┬────────┘
         │  List[FCDayPnL]
         ▼
┌─────────────────┐
│  Detect Agent    │  Compare against target ranges, flag breaches, assign color codes
└────────┬────────┘
         │  List[FCDayPnL] (with anomalies + color)
         ▼
┌─────────────────┐
│  Insight Agent   │  LLM-powered insights (Ollama) + rule-based fallback
└────────┬────────┘
         │  List[FCDayDigest]
         ▼
┌─────────────────┐
│  Notify Agent    │  Dispatch digest via configured channel (file/email/webhook)
└─────────────────┘
```

### Why This Decomposition

- Each agent is independently testable with known inputs/outputs
- The orchestrator can retry a failed agent without re-running the whole pipeline
- New agents (e.g., trend detection, forecast) plug in without changing existing ones
- This IS the "agentic AI workflow" the assignment asks for — each agent makes decisions about its domain, and the Insight Agent uses a local LLM for AI-powered analysis

## Agent Details

### 1. Ingest Agent

- Accepts CSV or Excel (xlsx/xls)
- Auto-detects columns by header text (flexible matching like Case 2)
- Handles multiple FCs in one file (FC column) or single-FC files
- Validates: no missing revenue, no negative values (warns), date parsing
- Output: normalized `FCDayRecord` list

### 2. Compute Agent

- Pure math, no side effects
- CM1 = Revenue - Manpower Cost - Packaging Cost
- CM2 = CM1 - Power & Fuel - FC Rent - Equipment Rentals - Overheads
- Each cost line as % of revenue (handles zero-revenue days gracefully)
- CM1% = CM1 / Revenue _ 100, CM2% = CM2 / Revenue _ 100
- Output: `FCDayPnL` with all computed fields

### 3. Detect Agent

- Compares each cost-line % against its target range (from config)
- Compares CM1% and CM2% against their targets (with ±3pp tolerance)
- Assigns daily color code: Red / Yellow / Green / Blue
- Each breach becomes an `Anomaly` record with line item, actual %, target range, severity
- Output: enriched `FCDayPnL` with `anomalies` list and `color_code`

### 4. Insight Agent (LLM-Powered)

- **Primary mode**: Uses a local LLM via Ollama (free, no API key) to generate contextual, natural-language insights
- **Fallback mode**: Rule-based templates if Ollama is not running — system always works
- For each FC-day with anomalies:
  1. Builds a structured prompt with: P&L numbers, anomaly list, color code, target ranges
  2. Sends to Ollama (llama3.2:3b or configurable model)
  3. LLM generates a contextual insight paragraph with reasoning, not just template fills
  4. Validates the response (must mention actual numbers, must not hallucinate new data)
- The LLM sees structured data and produces analysis — this is the "AI" in "agentic AI workflow"
- Why local LLM over cloud: free (assignment rule), low latency (same machine), no data leaves the system
- Why LLM over pure rules: generates richer insights ("this is the third consecutive day...", "combined with the Power & Fuel spike, this looks operational..."), varies phrasing naturally, handles unusual anomaly combinations that templates can't anticipate
- Output: `FCDayDigest` with insight text, anomaly list, color code, generation_mode (llm/rule)

### 5. Notify Agent

- Pluggable dispatch: file (default), email (SMTP), webhook (Slack/custom)
- File mode: writes HTML digest to `data/digests/{date}_{fc}.html`
- Email mode: sends via SMTP (configurable in .env)
- Generates both per-FC digest and cross-FC summary
- Output: delivery confirmation per channel

## Orchestrator

`backend/app/pipeline/orchestrator.py` — chains all agents:

```python
async def run_pipeline(upload_id: str) -> PipelineResult:
    records = ingest_agent.run(file_path)
    pnl_data = compute_agent.run(records)
    flagged_data = detect_agent.run(pnl_data, config)
    digests = insight_agent.run(flagged_data)
    notify_agent.run(digests, channels)
    return PipelineResult(pnl_data, digests)
```

## Tech Stack

| Layer           | Technology                  | Why                                                              |
| --------------- | --------------------------- | ---------------------------------------------------------------- |
| Backend         | FastAPI                     | Async, auto-docs, same as Case 2                                 |
| Data processing | pandas                      | Efficient tabular computation                                    |
| DB              | SQLAlchemy 2.0 + SQLite WAL | Lightweight, no server needed                                    |
| Charts          | Recharts                    | React-native, lightweight, good for time series                  |
| Styling         | Tailwind CSS                | Consistent with Cases 1 & 2                                      |
| LLM             | Ollama (local)              | Free, no API key, data stays local                               |
| LLM model       | llama3.2:3b                 | Small (2GB), fast inference, good enough for structured analysis |
| LLM client      | httpx                       | Async HTTP to Ollama REST API                                    |
| Email           | Python smtplib              | Built-in, no dependencies                                        |
| Excel read      | openpyxl                    | Same as Case 2                                                   |
| Excel write     | openpyxl                    | Export P&L reports                                               |

## Repository Layout

```
case3-fc-pnl-monitor/
├── AGENTS.md
├── .env.example
├── .gitignore
├── README.md
├── docs/
│   ├── architecture.md
│   ├── data_model.md
│   ├── business_rules.md
│   ├── api.md
│   ├── design.md
│   └── phases.md
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── errors.py
│   │   ├── pipeline/
│   │   │   ├── __init__.py
│   │   │   ├── orchestrator.py
│   │   │   ├── ingest_agent.py
│   │   │   ├── compute_agent.py
│   │   │   ├── detect_agent.py
│   │   │   ├── insight_agent.py
│   │   │   └── notify_agent.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── storage.py
│   │   │   └── processor.py
│   │   └── api/
│   │       ├── __init__.py
│   │       ├── upload.py
│   │       ├── pnl.py
│   │       └── system.py
│   └── tests/
│       ├── __init__.py
│       ├── test_compute.py
│       ├── test_detect.py
│       ├── test_insight.py
│       ├── test_api.py
│       └── conftest.py
├── frontend/
│   └── src/
│       ├── api/
│       ├── components/
│       │   ├── Dashboard.tsx
│       │   ├── FCCard.tsx
│       │   ├── PnLTable.tsx
│       │   ├── AnomalyLog.tsx
│       │   ├── CostBreakdownChart.tsx
│       │   ├── TrendChart.tsx
│       │   └── DigestView.tsx
│       └── routes/
│           ├── UploadPage.tsx
│           ├── DashboardPage.tsx
│           ├── FCDetailPage.tsx
│           └── HistoryPage.tsx
├── sample_data/
│   ├── input/
│   │   └── fc_daily_data.xlsx
│   └── output/
│       ├── pnl_report.xlsx
│       ├── anomaly_log.json
│       └── digests/
└── scripts/
    ├── run.sh
    ├── run.ps1
    ├── dev.sh
    └── generate_sample_data.py
```

## Security

- No secrets in code — all config via .env
- File upload size limit (configurable, default 50MB)
- Input validation on all uploads (file type, column presence)
- No PII in this case study (FC names, cost numbers only)
- SQL injection prevented by SQLAlchemy ORM
