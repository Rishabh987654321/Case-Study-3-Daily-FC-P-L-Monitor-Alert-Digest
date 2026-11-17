# Case Study 3: Daily FC P&L Monitor & Alert Digest

## What it does

An agentic pipeline that ingests a fulfilment centre's daily cost/revenue data (CSV or Excel), computes CM1/CM2 contribution margins and per-line-item cost percentages, detects margin breaches and cost anomalies against configurable target ranges, generates plain-language insights about what happened and what to do (via a local LLM, with a deterministic rule-based fallback), and delivers color-coded daily digests — surfaced through a central dashboard that shows every FC's status across every day at a glance, instead of someone finding out three days late from a spreadsheet.

## Quick Start (under 15 minutes)

**Prerequisites:** Python 3.11+, Node.js 18+, npm. Ollama is optional (AI-powered insights; the system works without it).

**Option A — one command:**

```bash
chmod +x scripts/run.sh && ./scripts/run.sh    # macOS/Linux
```
```powershell
.\scripts\run.ps1                                # Windows
```

This creates a venv, installs backend deps, builds the frontend, and starts the server at **http://localhost:8000**.

**Option B — manual:**

```bash
cd backend && python -m venv .venv && source .venv/bin/activate   # .venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt
cd ../frontend && npm install && npm run build
cd ../backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then open http://localhost:8000, upload `sample_data/input/fc_daily_data.xlsx`, and watch the dashboard populate.

## The Agentic Architecture

**Why agents, not one big function:** a monolithic "process_file()" function that parses, computes, flags, and emails in one pass is hard to test (you can't verify the math without also faking a file and an SMTP server) and hard to extend (adding a trend-detection step means editing the one function everyone's afraid to touch). Splitting the work into five agents, each with a narrow, typed contract, means: each agent is independently unit-testable with plain data in and data out; a failure in one agent (e.g. the LLM call timing out) degrades gracefully instead of taking down the whole run; and a new capability — a trend agent, a forecast agent — plugs in as a new pipeline stage without touching the others. This is also, literally, what the assignment is asking for: an "agentic AI workflow," not a script that happens to call an LLM once.

```
CSV/Excel Upload
      │
      ▼
┌─────────────────┐
│  Ingest Agent    │  Parse, validate, normalize tabular data
└────────┬────────┘
         │  list[FCDayRecord]
         ▼
┌─────────────────┐
│  Compute Agent   │  CM1, CM2, %-of-revenue for each cost line
└────────┬────────┘
         │  list[FCDayPnL]
         ▼
┌─────────────────┐
│  Detect Agent    │  Compare against target ranges, flag breaches, assign color codes
└────────┬────────┘
         │  list[FCDayPnL] (+ anomalies, color_code)
         ▼
┌─────────────────┐
│  Insight Agent   │  LLM-powered insight (Ollama) + rule-based fallback
└────────┬────────┘
         │  list[FCDayDigest]
         ▼
┌─────────────────┐
│  Notify Agent    │  Dispatch digest via configured channel (file/email)
└─────────────────┘
```

1. **Ingest Agent** (`backend/app/pipeline/ingest_agent.py`) — parses CSV/Excel with flexible column matching ("Labour" or "Manpower Cost" both map to manpower cost; "Power & Fuel" or "Electricity" both map to power/fuel), auto-sniffs CSV delimiters (comma/semicolon/tab), parses dates safely across formats (ISO, day-first slash dates, "1-Nov-2026") without the classic day/month-swap bug, skips summary/total rows, and never crashes on bad data — it degrades a bad row to a warning, not a stack trace.
2. **Compute Agent** (`compute_agent.py`) — pure math, no I/O: CM1 = Revenue − Manpower − Packaging; CM2 = CM1 − Power&Fuel − Rent − Equipment − Overheads; both as % of revenue. Zero-revenue days short-circuit to 0% everywhere instead of dividing by zero.
3. **Detect Agent** (`detect_agent.py`) — compares every cost line against its target range and CM1/CM2 against their ±3pp-tolerant targets, assigns the RED/YELLOW/GREEN/BLUE color code, and emits a typed `Anomaly` (line item, actual vs. target, deviation, severity) for every breach.
4. **Insight Agent** (`insight_agent.py`) — the AI step. Builds a structured prompt from the P&L numbers and anomaly list, sends it to a local LLM (Ollama), validates the response (length, sentence count, references real numbers), and falls back to deterministic rule-based templates if the LLM is unavailable, too slow, or hallucinates. See below for the full walkthrough.
5. **Notify Agent** (`notify_agent.py`) — renders the per-FC HTML digest and a cross-FC daily summary, and dispatches them via a pluggable channel: `file` (default, writes to `data/digests/`), or `email` (SMTP, falls back to file if unconfigured).

## Why a Local LLM (Ollama)

- The assignment requires an "agentic AI workflow" — the Insight Agent is the AI-powered step, not a decoration.
- Uses **Ollama with `llama3.2:3b`**: local, free, no API key, no per-call cost, and no data leaves the machine — this matters because the input is real financial data.
- The LLM sees the full structured P&L + anomaly context and writes connected analysis ("driven mainly by X, compounded by Y") instead of filling in a template's blanks — richer, and it reads like a sentence a person would actually write.
- **It is never a single point of failure.** `INSIGHT_MODE=auto` tries the LLM first and falls back to rule-based templates on any failure — timeout, connection refused, or a response that fails validation. `INSIGHT_MODE=rule` skips the LLM entirely (used by the test suite, so CI never depends on a running model). `INSIGHT_MODE=llm` is strict (raises instead of silently falling back) for when you explicitly want to know the LLM path broke.
- **Validation guards against hallucination**: the response must be 1–6 sentences, 20–1000 characters, and must contain at least one of the day's actual CM1%/CM2% figures — a response that doesn't reference the real numbers is rejected and the system falls back to the rule-based template instead of shipping a plausible-sounding but ungrounded insight.
- **A whole upload is time-bounded, not just one call.** In `auto` mode, the batch is given a total wall-clock budget (`INSIGHT_BATCH_BUDGET_SECONDS`, default 8s) for *all* its LLM attempts combined. Once that's spent, every remaining FC-day in that upload falls back to rule-based instantly — no LLM round trip attempted at all. Without this, a 10-row file costs at most 10× the per-call timeout, but a 1,000-row file would cost up to 1,000×, which turns "slow" into "the demo hangs for 15 minutes." `INSIGHT_MODE=llm` (strict) intentionally ignores this budget, since choosing strict mode means you've already said "always use the LLM, no silent shortcuts."

**How to set up Ollama (optional but recommended):**

```bash
# Install: https://ollama.com/download
ollama pull llama3.2:3b     # ~2GB download, one time
ollama serve                 # runs on localhost:11434
# The app detects it automatically via OLLAMA_BASE_URL — no other config needed.
# Without it, INSIGHT_MODE=auto (the default) transparently uses rule-based templates.
```

**A real-world note from building this**: on this project's dev machine (CPU-only, no GPU), `llama3.2:3b` takes roughly 30–70 seconds to generate a full ~150–200 token insight — and that's *while already warm*; loading the model from cold adds another ~9–10 seconds on top. Both numbers are well past the defaults (`OLLAMA_TIMEOUT=10`, `INSIGHT_BATCH_BUDGET_SECONDS=8`), and those defaults are intentional — left as specified in `business_rules.md`, not loosened just to chase more LLM hits. The honest consequence, verified by actually running it, not assumed: **at the defaults, on hardware this slow, `auto` mode will reliably produce `generation_mode: "rule"` for every row, regardless of file size** — the one attempt it's allowed never finishes in time. That's not a bug; it's the system correctly choosing "fast and bounded" over "wait and hope," and the rule-based output is still real, grounded, non-placeholder text (see examples below).

To actually *see* the LLM respond (e.g. for a demo), you need to deliberately give it enough time: use `INSIGHT_MODE=llm` (which ignores the batch budget entirely) with `OLLAMA_TIMEOUT=90` or so, on a small file (1–3 rows) so you're only waiting on one or two calls, not racing a shared budget across dozens. That's how the real LLM output quoted below was produced and verified. On a GPU, or simply faster CPU hardware, generation is fast enough that the *defaults* would work as originally designed — most rows completing inside the budget, a genuine mix of `"llm"` and `"rule"` — this machine's specific slowness is what pushes it to one extreme.

## Business Rules

```
CM1 = Revenue − Manpower Cost − Packaging Cost
CM2 = CM1 − Power & Fuel − FC Rent − Equipment Rentals − Overheads
CM1% = CM1 / Revenue × 100       CM2% = CM2 / Revenue × 100
```

Zero revenue ⇒ all percentages are set to 0 (never divide by zero) and the day is flagged `ZERO_REVENUE`.

| Cost line | Target % of revenue |
|---|---|
| Manpower | 20–28% |
| Packaging | 5–10% |
| Power & Fuel | 3–7% |
| FC Rent | 8–15% |
| Equipment Rentals | 2–5% |
| Overheads | 3–7% |

| Margin | Target | Flagged when |
|---|---|---|
| CM1% | 65–70% | < 62% or > 73% (±3pp tolerance) |
| CM2% | 15–30% | < 12% or > 33% (±3pp tolerance) |

**Color code** (by CM2%): 🔴 Red `<12%` · 🟡 Yellow `12–14.9%` or `30–32.9%` · 🟢 Green `15–30%` · 🔵 Blue `>33%` ("suspicious" — see below).

**A finding worth knowing before you retune these thresholds**: the six per-line ranges and the CM2 target aren't arithmetically independent. Sum every line at its *maximum* and total cost is 72% of revenue — a CM2 floor of 28%. Sum every line at its *midpoint* (a perfectly ordinary-looking day) and total cost is 56.5% — CM2 of 43.5%, which is **Blue**, despite zero individual line-item breaches. In other words: with these specific defaults, a "typical" day looks suspicious, and a "healthy Green" day requires costs pushed toward the top of each individual range. That's not a bug in this implementation — it's a property of the thresholds in `docs/business_rules.md` — but it's exactly the kind of thing Blue is supposed to catch (see `sample_data/spike_findings.md` for the full derivation and how the sample data was built around it).

## How the Insight Generation Works

Take FC-Delhi on 2026-11-05: Manpower 36.0% (target max 28%), Power & Fuel 11.0% (target max 7%), FC Rent 23.0% (target max 15%), CM2 crashed to 8.5% (Red, floor is 12%).

**With Ollama (LLM mode)** — actual output from this project's `llama3.2:3b`, verified live:

> Key finding: FC-Delhi is experiencing a margin crisis, with CM1 and CM2 deviating significantly from their targets, resulting in a revenue loss of 10.5% and 6.5% respectively. Top cost drivers: Manpower (36.0% vs target 20–28%), FC Rent (23.0% vs target 8–15%), and Power & Fuel (11.0% vs target 3–7%) are the top cost drivers, with deviations of +8.0pp, +8.0pp, and +4.0pp respectively. Recommendation: Reduce FC Rent expenses by 8.0pp to bring it within the target range of 8–15%. This action will help alleviate the margin crisis and improve overall profitability.

The agent: (1) builds a structured prompt with every P&L number, the anomaly list, color code, and target ranges; (2) POSTs it to Ollama's `/api/generate`; (3) the model connects the dots across all three breaches instead of listing them independently; (4) the response is validated (length, sentence count via a decimal-point-aware splitter — "8.0pp" must not be read as a sentence boundary — and must cite a real CM1%/CM2% figure); (5) ships it with `generation_mode: "llm"`.

**Without Ollama (rule-based fallback)** — real output from the sample data run, `generation_mode: "rule"`:

> On 2026-11-05, FC-Delhi CM2 = 8.5% (below 12%). Manpower Cost at 36.0% (target max 28.0%); FC Rent at 23.0% (target max 15.0%); Power & Fuel at 11.0% (target max 7.0%). Recommend immediate cost audit.

The agent: (1) reads the anomaly profile off the `FCDayPnL` (CM2 breach ⇒ Red template); (2) ranks the line-item breaches by impact (`|actual% − target midpoint| × revenue`, so a small deviation on a high-revenue day outranks a large deviation on a small one); (3) fills the template with the top 3 ranked breaches and the real numbers; (4) appends the recommended action for that scenario.

A Blue (suspicious) example, same mechanism, zero line-item breaches — the margin itself is the anomaly:

> On 2026-11-06, FC-Bangalore CM2 = 43.5% (above 33% — suspiciously high). Verify that all costs are reported, especially: Equipment Rentals at 3.5% (target min 2.0%); Power & Fuel at 5.0% (target min 3.0%); Overheads at 5.0% (target min 3.0%). Recommend reconciliation with actuals.

And a clean Green day:

> All metrics within target ranges for FC-Delhi on 2026-11-01. CM2 = 30.0% (Green).

All three are in `sample_data/output/digests/`, generated from an actual run, not written by hand.

## Results on Sample Data

From `sample_data/input/fc_daily_data.xlsx` (3 FCs × 30 days, one row deliberately omitted — see `docs/phases.md` Phase 0):

- **FCs analyzed:** 3 (FC-Delhi, FC-Mumbai, FC-Bangalore)
- **Days analyzed:** 30 (2026-11-01 to 2026-11-30), **89 FC-day records**
- **Color distribution:** 🟢 Green 78 (87.6%) · 🟡 Yellow 3 (3.4%) · 🔴 Red 5 (5.6%) · 🔵 Blue 3 (3.4%)
- **Total anomalies:** 45
- **Processing time:** end-to-end (ingest → compute → detect → insight(rule) → notify → persist) completes in **under 1 second**

Three concrete anomalies (full detail in `sample_data/output/anomaly_log.json`):

| FC | Date | Line item | Actual | Target | Severity |
|---|---|---|---|---|---|
| FC-Delhi | 2026-11-18 | CM2 | 70.5% | 15–30% | HIGH (Blue — extreme under-booking) |
| FC-Mumbai | 2026-11-27 | CM2 | 58.0% | 15–30% | HIGH (Blue) |
| FC-Delhi | 2026-11-05 | Manpower Cost | 36.0% | 20–28% | MEDIUM (contributing to the Red day above) |

## Configuration

All thresholds and channels are set via `.env` (copy `.env.example`). Nothing requires a code change to retune.

| Variable | Default | Meaning |
|---|---|---|
| `PORT`, `HOST` | `8000`, `0.0.0.0` | Server bind address |
| `DATABASE_URL` | `sqlite:///./data/pnl_monitor.db` | SQLite path (resolved against the project root regardless of CWD) |
| `MAX_FILE_MB` | `50` | Upload size limit |
| `UPLOAD_DIR` | `./data/uploads` | Where raw uploaded files are stored |
| `TARGET_MANPOWER_MIN/MAX` | `20` / `28` | Manpower %-of-revenue target |
| `TARGET_PACKAGING_MIN/MAX` | `5` / `10` | Packaging target |
| `TARGET_POWER_FUEL_MIN/MAX` | `3` / `7` | Power & Fuel target |
| `TARGET_RENT_MIN/MAX` | `8` / `15` | FC Rent target |
| `TARGET_EQUIPMENT_MIN/MAX` | `2` / `5` | Equipment Rentals target |
| `TARGET_OVERHEADS_MIN/MAX` | `3` / `7` | Overheads target |
| `TARGET_CM1_MIN/MAX`, `TARGET_CM2_MIN/MAX` | `65/70`, `15/30` | Margin targets |
| `CM_TOLERANCE` | `3` | ±pp tolerance before a margin breach is flagged |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Where to reach Ollama |
| `OLLAMA_MODEL` | `llama3.2:3b` | Model name to call |
| `OLLAMA_TIMEOUT` | `10` | Seconds before a single LLM call falls back to rules |
| `INSIGHT_MODE` | `auto` | `auto` (LLM then fallback) / `llm` (strict) / `rule` (templates only) |
| `INSIGHT_BATCH_BUDGET_SECONDS` | `8` | `auto` mode only: total seconds the *whole upload* may spend attempting LLM calls before every remaining row in it falls back to rule-based instantly, regardless of row count |
| `NOTIFY_CHANNEL` | `file` | `file` or `email` |
| `SMTP_HOST/PORT/USER/PASSWORD`, `DIGEST_RECIPIENTS` | — | Required only for `NOTIFY_CHANNEL=email`; falls back to file if left blank |

**To change thresholds:** edit the `TARGET_*` values in `.env` and restart — every upload processed after that uses the new ranges (`GET /api/config` reflects whatever is currently loaded).

**To enable email:** set `NOTIFY_CHANNEL=email`, fill in `SMTP_HOST/PORT/USER/PASSWORD` (e.g. a Gmail app password) and `DIGEST_RECIPIENTS` (comma-separated). If `SMTP_USER` is blank, the system silently uses file mode instead of failing.

## How This System Could Get Smarter Over Time

1. **Memory of past days.** Today every upload is analyzed in isolation. Storing rolling averages per FC and detecting *trends* — "Manpower has been above target for 5 consecutive days" — is a more useful alert than five independent daily breaches that each look like a one-off.
2. **Adaptive thresholds.** Fixed global ranges mean a tier-1-city FC with structurally higher rent gets flagged every single day. Learning each FC's own historical baseline (e.g. a rolling 90-day percentile band) and flagging deviation *from that FC's normal*, not a one-size-fits-all number, would cut false positives sharply.
3. **Anomaly correlation.** When Power & Fuel and Overheads spike together, that's probably one event (a generator running through a grid outage), not two unrelated problems. A correlation step that groups simultaneous breaches into one root-cause hypothesis would turn five alerts into one actionable one.
4. **Manual overrides / acknowledgement.** Let a compliance user mark a flagged day as "acknowledged — Diwali week, expected" so it stops re-alerting every time the dashboard refreshes, while still being visible in the audit trail.
5. **Trend forecasting.** A simple moving-average or exponential-smoothing model over each FC's CM2% history could warn "CM2 is on track to breach 12% within 4 days at the current rate" *before* it happens, not after.
6. **Larger models, given the budget.** `llama3.2:3b` is deliberately small so it runs free on a laptop. With more local compute, a 7B/13B model gets noticeably better at connecting indirect signals. With a paid API budget, a frontier model could do genuine multi-step reasoning across the FC's history: "this is the third consecutive Friday with elevated overtime — consider restructuring the weekend shift," which requires remembering last Friday, not just reading today's row.
7. **Multi-month / cross-FC comparison.** This month vs. last month, this FC vs. its three closest peers by revenue tier, seasonal adjustment (festival weeks, monsoon logistics delays) — all absent today; the system currently only ever looks at the file it was just given.
8. **Automated escalation.** Red for 3+ consecutive days → auto-notify the regional head, not just color a cell red on a dashboard someone has to remember to check. Blue for 2+ days → auto-trigger a cost-reconciliation workflow instead of waiting for a human to notice the suspicious pattern.

## Known Limitations

- LLM insights require Ollama running locally; without it (or if it's too slow — see the Ollama section above), the system automatically and silently uses rule-based templates. Both are demonstrated in this submission.
- The `auto`-mode batch budget trades "guaranteed real LLM insights" for "guaranteed bounded time." On slow (CPU-only) hardware, a large upload will reliably show `generation_mode: "rule"` for every row, not a mix — the budget runs out before even one full generation completes. This is intentional (a hanging demo is worse than an all-rule-based one), but it means the budget and "see the LLM actually respond" are in tension for big files on slow machines; use a small file + `INSIGHT_MODE=llm` + a larger `OLLAMA_TIMEOUT` to demo the LLM path specifically.
- Batch-file only — no real-time/streaming ingestion; a day's data has to be uploaded, not pushed live.
- Email notification requires manual SMTP configuration; it is not zero-config (file-based digests are, and are the default).
- HTML digests use plain tables for email-client compatibility — no client-side JS charts in the emailed digest (the web dashboard has full Recharts visualizations).
- Target ranges are global per deployment, not per-FC — the "adaptive thresholds" improvement above addresses this; today retuning a range affects every FC.
- No authentication — this is a single-user/trusted-network app, matching the assignment's scope (no PII, no auth requirement specified).
- Duplicate `(FC, date)` rows in an upload are all kept and flagged with a warning at ingest time, but the dashboard's daily grid (one cell per FC-day) can only display one color per cell, so it shows the last of the duplicates; the full `/pnl` list and the Excel export still contain every row.
- At larger scale (~1,000+ rows), the Notify Agent's per-row HTML file writes are the dominant cost (~5s of a ~6s run for 1,100 rows) since each digest is written as its own file synchronously; batching or async writes would be the next optimization before this became a real bottleneck.

## Project Structure

```
case3-fc-pnl-monitor/
├── AGENTS.md                 # Rules this project was built under
├── .env.example               # All config, documented
├── docs/                      # Design docs (architecture, business rules, API, data model, UI)
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, CORS, error handlers, serves the built frontend
│   │   ├── config.py           # Settings (.env-driven), TargetRange
│   │   ├── types.py            # Core pipeline Pydantic models (FCDayRecord, FCDayPnL, Anomaly, ...)
│   │   ├── models.py           # SQLAlchemy ORM (uploads, fc_days, anomalies, digests)
│   │   ├── schemas.py          # API request/response Pydantic models
│   │   ├── pipeline/            # The 5 agents + orchestrator + Excel report writer
│   │   ├── services/            # storage.py (file I/O), processor.py (background pipeline run)
│   │   └── api/                 # upload.py, pnl.py, system.py routers
│   ├── cli.py                  # Standalone CLI: run the pipeline on a file, print a report
│   └── tests/                  # pytest — 76 tests across every agent + the API
├── frontend/
│   └── src/
│       ├── api/                 # typed client
│       ├── components/          # ColorGrid, TrendChart, CostBreakdownChart, PnLTable, ...
│       └── routes/              # UploadPage, DashboardPage, FCDetailPage, HistoryPage
├── sample_data/
│   ├── input/fc_daily_data.xlsx  # Generated sample data, all 4 scenarios planted
│   ├── output/                   # Real artifacts from an actual run (not hand-written)
│   └── spike_findings.md         # Phase 0 data-generation + threshold-math findings
└── scripts/                     # run.sh/.ps1 (production), dev.sh/.ps1 (hot-reload dev)
```
