# Business Rules — FC P&L Monitor

## P&L Computation

### Contribution Margins

```
CM1 = Revenue − Manpower Cost − Packaging Cost
CM2 = CM1 − Power & Fuel − FC Rent − Equipment Rentals − Overheads
     = Revenue − ALL costs

CM1% = (CM1 / Revenue) × 100
CM2% = (CM2 / Revenue) × 100
```

### Cost Line Items as % of Revenue

Each cost line is expressed as a percentage of revenue for that FC on that day:

```
cost_pct = (cost_amount / revenue) × 100
```

### Zero Revenue Handling

If revenue = 0 for a day, all percentages are set to 0 and the day is flagged with a special "ZERO_REVENUE" anomaly. Division by zero must never crash the system.

## Target Ranges

### Per-Line-Item Targets (% of Revenue)

These are configurable via .env. Defaults based on typical FC economics:

| Cost Line         | Min % | Max % | .env Variable                                |
| ----------------- | ----- | ----- | -------------------------------------------- |
| Manpower Cost     | 20    | 28    | TARGET_MANPOWER_MIN, TARGET_MANPOWER_MAX     |
| Packaging Cost    | 5     | 10    | TARGET_PACKAGING_MIN, TARGET_PACKAGING_MAX   |
| Power & Fuel      | 3     | 7     | TARGET_POWER_FUEL_MIN, TARGET_POWER_FUEL_MAX |
| FC Rent           | 8     | 15    | TARGET_RENT_MIN, TARGET_RENT_MAX             |
| Equipment Rentals | 2     | 5     | TARGET_EQUIPMENT_MIN, TARGET_EQUIPMENT_MAX   |
| Overheads         | 3     | 7     | TARGET_OVERHEADS_MIN, TARGET_OVERHEADS_MAX   |

### Margin Targets

| Metric | Target Range | Tolerance | .env Variables                                       |
| ------ | ------------ | --------- | ---------------------------------------------------- |
| CM1%   | 65–70%       | ±3 pp     | TARGET_CM1_MIN=65, TARGET_CM1_MAX=70, CM_TOLERANCE=3 |
| CM2%   | 15–30%       | ±3 pp     | TARGET_CM2_MIN=15, TARGET_CM2_MAX=30, CM_TOLERANCE=3 |

**Tolerance rule:** Flag when CM1% or CM2% deviates more than ±3 percentage points from the target range. So CM1% is flagged if < 62% or > 73%. CM2% is flagged if < 12% or > 33%.

## Anomaly Detection

### What Gets Flagged

1. **Line item breach**: Any cost line's %-of-revenue falls outside its target range
2. **CM1 breach**: CM1% outside target ± tolerance
3. **CM2 breach**: CM2% outside target ± tolerance
4. **Zero revenue**: Revenue = 0 for a day

### Anomaly Record

Each anomaly produces:

```
{
  date, fc_name, line_item, actual_pct, target_min, target_max, status,
  deviation: how far outside the range (negative = below min, positive = above max)
}
```

Status values: `BREACH_LOW`, `BREACH_HIGH`, `ZERO_REVENUE`

## FC Daily Color Code

Based on CM2% for that FC on that day:

| Color     | CM2% Range           | Meaning                                    |
| --------- | -------------------- | ------------------------------------------ |
| 🔴 Red    | < 12%                | Margin crisis — immediate attention        |
| 🟡 Yellow | 12–14.9% OR 30–32.9% | Warning zone — approaching limits          |
| 🟢 Green  | 15–30%               | Healthy — within target                    |
| 🔵 Blue   | > 33%                | Suspicious — check for underreported costs |

Note: The blue zone is counterintuitive — high margin is suspicious because it may indicate costs that haven't been booked yet.

## Insight Generation Rules

### Primary Mode: LLM-Powered (Ollama)

The Insight Agent uses a local LLM via Ollama to generate contextual, natural-language insights. This is the "AI" in the agentic workflow.

**Prompt structure sent to Ollama:**

```
You are an FC financial analyst. Analyze this daily P&L data and write a concise insight paragraph.

FC: {fc_name}
Date: {date}
Revenue: ₹{revenue}
CM1: {cm1}% (target: 65-70%)
CM2: {cm2}% (target: 15-30%)
Color Code: {color} ({color_meaning})

Cost Breakdown (% of Revenue):
- Manpower: {manpower_pct}% (target: 20-28%)
- Packaging: {packaging_pct}% (target: 5-10%)
- Power & Fuel: {power_pct}% (target: 3-7%)
- FC Rent: {rent_pct}% (target: 8-15%)
- Equipment Rentals: {equipment_pct}% (target: 2-5%)
- Overheads: {overheads_pct}% (target: 3-7%)

Anomalies detected:
{anomaly_list_with_deviations}

Write 2-3 sentences: state the key finding, identify the top cost driver(s), and recommend one specific action. Use actual numbers. Be direct.
```

**LLM response validation:**

- Must be 1-4 sentences (reject and retry or fall back if not)
- Must reference at least one actual number from the data
- Must not introduce numbers not in the input (hallucination guard)
- Timeout: 10 seconds per call (fall back to templates on timeout)

**Configuration (.env):**

```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_TIMEOUT=10
INSIGHT_MODE=auto  # auto | llm | rule
```

`INSIGHT_MODE=auto`: Try LLM first, fall back to templates. `llm`: LLM only (fail if Ollama down). `rule`: Templates only (skip LLM).

### Fallback Mode: Rule-Based Templates

When Ollama is unavailable or the LLM response fails validation, the system falls back to deterministic templates. The insight agent selects a template based on the day's anomaly profile:

1. **No anomalies** → "All metrics within target ranges for {fc} on {date}. CM2 = {cm2}% (Green)."

2. **CM2 breach (Red)** → "On {date}, {fc} CM2 = {cm2}% (below {threshold}%). {top_n_breaches}. Recommend immediate cost audit."

3. **CM2 breach (Blue)** → "On {date}, {fc} CM2 = {cm2}% (above 33% — suspiciously high). Verify that all costs are reported, especially: {lowest_pct_items}. Recommend reconciliation with actuals."

4. **Yellow zone** → "On {date}, {fc} CM2 = {cm2}% (approaching {direction} limit). Watch: {breach_items}."

5. **Line-item only breach (CM2 still Green)** → "On {date}, {fc} margins are healthy (CM2 = {cm2}%) but {n} line items breached targets: {items}. No immediate action needed but monitor."

### Breach Ranking

Within each insight, breaches are sorted by impact:

```
impact = |actual_pct - midpoint(target_range)| × revenue
```

This ensures high-revenue FCs' small percentage deviations get appropriate attention.

### Recommended Actions

| Scenario                 | Action                                                             |
| ------------------------ | ------------------------------------------------------------------ |
| Single line-item high    | "Review {item} spend — {x}pp above target max"                     |
| Multiple line-items high | "Cost audit needed — {n} items above target"                       |
| CM2 Red                  | "Immediate cost review. Escalate to FC head."                      |
| CM2 Blue                 | "Reconcile costs with actuals. Check for unbilled {items}."        |
| CM1 breach               | "Review direct costs (manpower + packaging)"                       |
| Zero revenue             | "Verify data: zero revenue recorded. Check if FC was operational." |

## Digest Format

### Per-FC Daily Digest

```
═══════════════════════════════════════════
  {FC Name} — Daily P&L Digest
  {Date} | Status: {Color Badge}
═══════════════════════════════════════════

  Revenue:          ₹{revenue}
  CM1:              ₹{cm1} ({cm1_pct}%)
  CM2:              ₹{cm2} ({cm2_pct}%)

  Cost Breakdown:
  ├── Manpower:     {manpower_pct}% ({status})
  ├── Packaging:    {packaging_pct}% ({status})
  ├── Power & Fuel: {power_pct}% ({status})
  ├── FC Rent:      {rent_pct}% ({status})
  ├── Equipment:    {equipment_pct}% ({status})
  └── Overheads:    {overheads_pct}% ({status})

  {insight_text}
═══════════════════════════════════════════
```

### Cross-FC Summary

A table showing all FCs for the day with their color codes and CM2%.
