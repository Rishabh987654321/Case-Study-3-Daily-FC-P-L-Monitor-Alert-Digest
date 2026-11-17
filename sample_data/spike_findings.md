# Spike Findings — Sample Data Generation

## Source data

All sample data was generated from scratch by
`scripts/generate_sample_data.py`.

## Key finding: the default per-line-item ranges and the CM2 margin target are only compatible near the top of each range

Before writing the generator, I checked whether the six per-line-item target
ranges (`docs/business_rules.md`) are arithmetically consistent with the CM2
target range (15–30%). They are not, in an important way:

```
Line item            min%   max%
Manpower              20     28
Packaging              5     10
Power & Fuel            3     7
FC Rent                 8     15
Equipment Rentals       2     5
Overheads               3     7
                      ----   ----
Sum                    41     72
```

CM2% = 100 − (sum of all six cost %). So:

| Scenario                       | Total cost% | Resulting CM2%          |
| ------------------------------ | ----------- | ----------------------- |
| Every line at its **minimum**  | 41          | **59%** (Blue)          |
| Every line at its **midpoint** | 56.5        | **43.5%** (Blue)        |
| Every line at its **maximum**  | 72          | **28%** (Green, barely) |

The maximum achievable total cost, with every single line item simultaneously
within its own target range, is 72% of revenue — which caps CM2% at a floor of
28%. In other words: **a day where every cost line sits at a "perfectly
normal" midpoint value produces CM2% = 43.5%, which is squarely in the Blue
"suspicious" zone, despite zero individual line-item anomalies.**

This isn't a bug in my data generation — it's a property of the default
thresholds as specified in `docs/business_rules.md` / `.env.example`. It
actually supports the business narrative well: Blue is described as
"suspicious — check for underreported costs," and this shows that _typical_
(midpoint) costs naturally look suspicious under these specific default
ranges unless costs are pushed toward the top of each range. I used this
directly in the data design:

- **"Clean" / Green days** are deliberately constructed with costs clustered
  near the _top_ of each individual range (total cost 70.0–71.8% of revenue),
  which is the only way to land CM2% inside 28–30% while staying within every
  individual range.
- **The "natural" Blue day** (`FC-Bangalore, 2026-11-06`) uses plain midpoint
  costs with zero line-item breaches — demonstrating that Blue can occur
  purely from the margin math, not from any flagged line item. This is the
  most interesting single example in the dataset.

If the per-line ranges are ever retuned, this constraint should be
re-verified (sum-of-maxes must stay ≥ 70 for the Green zone to be reachable
at all without a line-item breach).

## Generated file: `sample_data/input/fc_daily_data.xlsx`

### Sheet 1 — "Daily Data"

| Column            | Type     | Range observed                       |
| ----------------- | -------- | ------------------------------------ |
| FC Name           | string   | FC-Delhi, FC-Mumbai, FC-Bangalore    |
| Date              | datetime | 2026-11-01 to 2026-11-30             |
| Revenue           | int (₹)  | 0 (planted zero-rev day) to ~271,000 |
| Manpower Cost     | int (₹)  | 0 to ~95,000                         |
| Packaging Cost    | int (₹)  | 0 to ~40,000                         |
| Power & Fuel      | int (₹)  | 0 to ~30,000                         |
| FC Rent           | int (₹)  | 0 to ~66,000                         |
| Equipment Rentals | int (₹)  | 0 to ~15,000                         |
| Overheads         | int (₹)  | 0 to ~24,000                         |

89 rows (3 FCs × 30 days, minus 1 deliberately missing FC-day).

### Sheet 2 — "Target Ranges"

Reference table: 6 cost-line ranges + CM1 (65–70%) + CM2 (15–30%), both with
a "±3pp tolerance before flagging" note, matching `.env.example`.

## Row count per scenario type

| Scenario                                                  | Count | Resulting color                                        |
| --------------------------------------------------------- | ----- | ------------------------------------------------------ |
| Clean (all lines in range, no breach)                     | 74    | GREEN                                                  |
| Line-item-only breach (1 line out of range, CM2 still OK) | 4     | GREEN                                                  |
| CM2 breach                                                | 4     | RED                                                    |
| Suspiciously high CM2                                     | 3     | BLUE                                                   |
| Yellow zone (lower 12–14.9% or upper 30–32.9%)            | 3     | YELLOW                                                 |
| Zero revenue                                              | 1     | (RED/ZERO_REVENUE — handled specially by Detect Agent) |
| Missing FC-day (row omitted entirely)                     | 1     | n/a                                                    |

Clean days land at 74/89 ≈ 83% rather than the suggested "~60%" guideline.
I prioritized guaranteeing the required _minimum counts_ for every anomaly
type (Red/Blue/Yellow/line-item — each "at least 3-4" or "at least 2-3" per
the brief) over hitting an exact clean-day percentage, since forcing clean
days down to 60% would mean roughly a third of all days are anomalous, which
reads as unrealistic for a note about "day-to-day variation" in otherwise
healthy FCs. All specified minimums are met or exceeded.

Verified programmatically (not just by design intent) — every one of the 74
clean rows has CM1% ∈ [62.2, 63.0] and CM2% ∈ [28.8, 30.0], i.e. inside both
target bands with zero accidental breaches from the random jitter.

## Hand-calculated validation examples

### 1. Clean day — FC-Delhi, 2026-11-01 (GREEN)

```
Revenue = 213,400
CM1 = 213,400 − 59,199 − 20,471 = 133,730
CM1% = 133,730 / 213,400 × 100 = 62.67%   (target 65–70%, tolerance ±3 → flag if <62 or >73 → OK)
CM2 = 133,730 − 14,308 − 31,279 − 10,123 − 14,102 = 63,918
CM2% = 63,918 / 213,400 × 100 = 29.95%   (target 15–30% → OK, Green)

Manpower:   59,199 → 27.74%  (target 20–28%)  OK
Packaging:  20,471 →  9.59%  (target 5–10%)   OK
Power&Fuel: 14,308 →  6.70%  (target 3–7%)    OK
FC Rent:    31,279 → 14.66%  (target 8–15%)   OK
Equipment:  10,123 →  4.74%  (target 2–5%)    OK
Overheads:  14,102 →  6.61%  (target 3–7%)    OK

Expected color: GREEN. No anomalies.
```

### 2. CM2 breach — FC-Delhi, 2026-11-05 (RED)

```
Revenue = 237,400
CM1 = 237,400 − 85,464 − 22,553 = 129,383
CM1% = 129,383 / 237,400 × 100 = 54.50%   → BELOW 62 → CM1 breach (HIGH)
CM2 = 129,383 − 26,114 − 54,602 − 11,870 − 16,618 = 20,179
CM2% = 20,179 / 237,400 × 100 = 8.50%     → BELOW 12 → CM2 breach (HIGH), color RED

Manpower:   85,464 → 36.00%  (target 20–28%)  BREACH_HIGH (+8.0pp)
Packaging:  22,553 →  9.50%  (target 5–10%)   OK
Power&Fuel: 26,114 → 11.00%  (target 3–7%)    BREACH_HIGH (+4.0pp)
FC Rent:    54,602 → 23.00%  (target 8–15%)   BREACH_HIGH (+8.0pp)
Equipment:  11,870 →  5.00%  (target 2–5%)     OK (at max, inclusive)
Overheads:  16,618 →  7.00%  (target 3–7%)     OK (at max, inclusive)

Expected color: RED. Anomalies: CM1 (HIGH), CM2 (HIGH), Manpower (MEDIUM),
Power & Fuel (MEDIUM), FC Rent (MEDIUM).
```

### 3. Suspiciously high CM2 — FC-Bangalore, 2026-11-06 (BLUE)

```
Revenue = 154,100
CM1 = 154,100 − 36,984 − 11,558 = 105,558
CM1% = 105,558 / 154,100 × 100 = 68.50%   (target 65–70% → OK, well inside)
CM2 = 105,558 − 7,705 − 17,722 − 5,394 − 7,705 = 67,032
CM2% = 67,032 / 154,100 × 100 = 43.50%    → ABOVE 33 → CM2 breach (HIGH), color BLUE

Manpower:   36,984 → 24.00%  (target 20–28%)  OK
Packaging:  11,558 →  7.50%  (target 5–10%)   OK
Power&Fuel:  7,705 →  5.00%  (target 3–7%)    OK
FC Rent:    17,722 → 11.50%  (target 8–15%)   OK
Equipment:   5,394 →  3.50%  (target 2–5%)    OK
Overheads:   7,705 →  5.00%  (target 3–7%)    OK

Expected color: BLUE. Only anomaly: CM2 (HIGH, "suspiciously high" —
zero line-item breaches, which is exactly the point of this scenario).
```

### 4. Zero revenue — FC-Mumbai, 2026-11-10

```
Revenue = 0
Manpower = 5,000, Packaging = 0, Power = 2,000, Rent = 18,000, Equipment = 3,000, Overheads = 4,000

Per business_rules.md: revenue = 0 → all percentages set to 0 (no division
by zero), day flagged with a ZERO_REVENUE anomaly, color = RED.
This also exercises the "fixed costs continue even with no revenue" edge
case (rent/overheads/manpower still non-zero) for the Compute Agent.
```

## Edge cases included

1. **Zero revenue**: FC-Mumbai, 2026-11-10 — revenue 0, non-zero fixed costs
   still present (rent, overheads, skeleton manpower).
2. **Missing FC-day**: FC-Bangalore has no row at all for 2026-11-15 —
   exercises "not all FCs report every day."
3. **Natural variation**: revenue has a weekday pattern (Monday +6%,
   weekend −10%), a mild +0.3%/day upward trend, and ±5% random noise —
   not uniform-random, to look like real operational data.
4. **Boundary values**: several planted rows have a line item sitting exactly
   at its max (e.g. Equipment at 5.00%, Overheads at 7.00% in the RED day) to
   test that range checks are inclusive, not exclusive.

## Generation decisions

- **Seed fixed at `random.seed(42)`** for reproducibility — re-running the
  script produces identical output.
- **Per-FC base revenue** differs (Delhi 230k, Mumbai 190k, Bangalore 150k)
  so the three FCs aren't just noisy copies of each other.
- **Clean/Yellow-upper days use a retry-based solver** (`solve_margin_only_vector`)
  rather independent per-line jitter: five lines get random jitter near the
  top of their range, and the sixth (Overheads) is solved algebraically to
  hit an exact target total, retrying until Overheads itself lands inside its
  own range. This guarantees every clean day is mathematically Green with no
  accidental breaches, instead of hoping random jitter works out.
- **Red/Blue/Yellow(lower)/line-item-breach days are hand-specified exact
  vectors**, each checked by hand (see above) and by the generator's own
  self-check printout, rather than solved generically — there are few enough
  of these (4/3/3/4 respectively) that hardcoding with verification was
  simpler and safer than building a general constraint solver for the whole
  design space.
