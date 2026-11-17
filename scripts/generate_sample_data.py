"""Generate sample_data/input/fc_daily_data.xlsx for the FC P&L Monitor.

Deliberately plants every required scenario type (clean/Green, CM2 breach/Red,
line-item-only breach, suspiciously high CM2/Blue, Yellow) plus edge cases
(zero revenue, a missing FC-day) at known (fc, date) coordinates, so Phase 1
can be validated against known-good expected output.

Key design constraint (see sample_data/spike_findings.md for the full writeup):
with the default per-line-item ranges, the maximum achievable total cost is 72%
of revenue (every line at its max), which caps CM2% at 28% from below. So any
day where every cost line is within its individual range will have CM2% in the
narrow band [28, 30] if it's meant to be "Green". Conversely, a day where every
line sits at the midpoint of its own range (a perfectly "normal-looking" day)
produces CM2% = 43.5% -- solidly Blue -- with zero individual anomalies. Blue
days are therefore built using plain midpoint-ish costs, not extreme ones.
"""

import random
from datetime import date, timedelta

import pandas as pd

random.seed(42)

FCS = ["FC-Delhi", "FC-Mumbai", "FC-Bangalore"]
START_DATE = date(2026, 11, 1)
NUM_DAYS = 30
DATES = [START_DATE + timedelta(days=i) for i in range(NUM_DAYS)]

BASE_REVENUE = {"FC-Delhi": 230_000, "FC-Mumbai": 190_000, "FC-Bangalore": 150_000}

RANGES = {
    "manpower": (20.0, 28.0),
    "packaging": (5.0, 10.0),
    "power_fuel": (3.0, 7.0),
    "fc_rent": (8.0, 15.0),
    "equipment": (2.0, 5.0),
    "overheads": (3.0, 7.0),
}

LINE_ORDER = ["manpower", "packaging", "power_fuel", "fc_rent", "equipment", "overheads"]

COL_MAP = {
    "manpower": "Manpower Cost",
    "packaging": "Packaging Cost",
    "power_fuel": "Power & Fuel",
    "fc_rent": "FC Rent",
    "equipment": "Equipment Rentals",
    "overheads": "Overheads",
}


def revenue_for(fc: str, day: date, day_index: int) -> float:
    """Base revenue with weekday pattern, a mild upward trend, and noise."""
    base = BASE_REVENUE[fc]
    weekday = day.weekday()  # Monday=0 .. Sunday=6
    weekday_factor = 1.0
    if weekday == 0:  # Monday bump (post-weekend order backlog)
        weekday_factor = 1.06
    elif weekday >= 5:  # weekend dip
        weekday_factor = 0.90
    trend_factor = 1.0 + 0.003 * day_index
    noise_factor = random.uniform(0.95, 1.05)
    return round(base * weekday_factor * trend_factor * noise_factor, -2)


def solve_margin_only_vector(total_target_range: tuple[float, float], max_tries: int = 500) -> dict:
    """Pick manpower/packaging/power/rent/equipment near the top of their ranges
    with jitter, then solve overheads to land the total exactly in range.
    Produces a day where every line is within its individual range (no breach),
    purely varying the blended margin outcome."""
    for _ in range(max_tries):
        total_target = random.uniform(*total_target_range)
        m = RANGES["manpower"][1] - random.uniform(0.1, 0.9)
        p = RANGES["packaging"][1] - random.uniform(0.05, 0.6)
        pw = RANGES["power_fuel"][1] - random.uniform(0.05, 0.5)
        r = RANGES["fc_rent"][1] - random.uniform(0.1, 1.2)
        e = RANGES["equipment"][1] - random.uniform(0.05, 0.4)
        o = total_target - (m + p + pw + r + e)
        if RANGES["overheads"][0] <= o <= RANGES["overheads"][1]:
            return {"manpower": m, "packaging": p, "power_fuel": pw, "fc_rent": r,
                    "equipment": e, "overheads": o}
    raise RuntimeError(f"Could not solve margin-only vector for target {total_target_range}")


def pct_of(vec: dict) -> float:
    return sum(vec.values())


def cm2_of(vec: dict) -> float:
    return round(100 - pct_of(vec), 2)


def breaches(vec: dict) -> list[str]:
    out = []
    for k, v in vec.items():
        lo, hi = RANGES[k]
        if v < lo or v > hi:
            out.append(f"{k}={v:.1f} (range {lo}-{hi})")
    return out


# ---------------------------------------------------------------------------
# Explicitly planted scenario vectors, keyed by (fc, date offset from Nov 1).
# Each tuple is (label, cost_pct_vector). Verified by hand in spike_findings.md.
# ---------------------------------------------------------------------------

SPECIAL: dict[tuple[str, int], tuple[str, dict]] = {
    # --- RED: CM2 < 12% (4 days, different breach combinations) ---
    ("FC-Delhi", 4): ("RED_manpower_power_rent", {
        "manpower": 36.0, "packaging": 9.5, "power_fuel": 11.0,
        "fc_rent": 23.0, "equipment": 5.0, "overheads": 7.0,
    }),
    ("FC-Mumbai", 11): ("RED_packaging_overheads_rent", {
        "manpower": 26.0, "packaging": 17.0, "power_fuel": 5.5,
        "fc_rent": 25.0, "equipment": 3.5, "overheads": 14.0,
    }),
    ("FC-Bangalore", 19): ("RED_manpower_equipment_power", {
        "manpower": 40.0, "packaging": 8.5, "power_fuel": 14.0,
        "fc_rent": 13.0, "equipment": 10.0, "overheads": 6.5,
    }),
    ("FC-Delhi", 24): ("RED_manpower_rent", {
        "manpower": 36.0, "packaging": 9.5, "power_fuel": 7.0,
        "fc_rent": 28.0, "equipment": 4.5, "overheads": 6.8,
    }),

    # --- LINE-ITEM-ONLY BREACH: CM2 stays Green, exactly one line breaches ---
    ("FC-Mumbai", 2): ("LINEITEM_packaging_only", {
        "manpower": 25.0, "packaging": 12.0, "power_fuel": 6.8,
        "fc_rent": 14.8, "equipment": 4.7, "overheads": 6.8,
    }),
    ("FC-Bangalore", 7): ("LINEITEM_overheads_only", {
        "manpower": 27.5, "packaging": 9.5, "power_fuel": 6.8,
        "fc_rent": 14.5, "equipment": 4.7, "overheads": 9.0,
    }),
    ("FC-Delhi", 13): ("LINEITEM_equipment_only", {
        "manpower": 27.0, "packaging": 9.6, "power_fuel": 6.6,
        "fc_rent": 14.6, "equipment": 7.0, "overheads": 6.6,
    }),
    ("FC-Mumbai", 21): ("LINEITEM_manpower_only", {
        "manpower": 30.0, "packaging": 7.0, "power_fuel": 7.0,
        "fc_rent": 15.0, "equipment": 4.6, "overheads": 6.6,
    }),

    # --- BLUE: CM2 > 33% ---
    ("FC-Bangalore", 5): ("BLUE_natural_no_breach", {
        "manpower": 24.0, "packaging": 7.5, "power_fuel": 5.0,
        "fc_rent": 11.5, "equipment": 3.5, "overheads": 5.0,
    }),
    ("FC-Delhi", 17): ("BLUE_extreme_underbooked", {
        "manpower": 16.0, "packaging": 3.0, "power_fuel": 1.5,
        "fc_rent": 6.0, "equipment": 1.0, "overheads": 2.0,
    }),
    ("FC-Mumbai", 26): ("BLUE_partial_underbooked", {
        "manpower": 18.0, "packaging": 4.0, "power_fuel": 4.0,
        "fc_rent": 9.0, "equipment": 3.0, "overheads": 4.0,
    }),

    # --- YELLOW: CM2 in 12-14.9% (lower) or 30-32.9% (upper) ---
    ("FC-Delhi", 8): ("YELLOW_lower_manpower_power_rent", {
        "manpower": 34.0, "packaging": 9.8, "power_fuel": 9.5,
        "fc_rent": 21.0, "equipment": 4.8, "overheads": 7.0,
    }),
    ("FC-Bangalore", 15): ("YELLOW_upper_no_breach", {
        "manpower": 27.0, "packaging": 9.2, "power_fuel": 6.5,
        "fc_rent": 13.8, "equipment": 4.3, "overheads": 6.3,
    }),
    ("FC-Mumbai", 22): ("YELLOW_lower_packaging_rent_overheads", {
        "manpower": 28.0, "packaging": 15.0, "power_fuel": 6.3,
        "fc_rent": 22.0, "equipment": 4.3, "overheads": 10.0,
    }),

    # --- ZERO REVENUE edge case ---
    ("FC-Mumbai", 9): ("ZERO_REVENUE", None),
}

# MISSING FC-DAY edge case: FC-Bangalore simply has no row on this date.
MISSING_ROW = ("FC-Bangalore", 14)

ZERO_REVENUE_FIXED_COSTS = {
    "manpower_cost": 5000, "packaging_cost": 0, "power_fuel": 2000,
    "fc_rent": 18000, "equipment_rentals": 3000, "overheads": 4000,
}


def main() -> None:
    rows = []
    labels = []  # parallel list for the findings report

    for day_idx, day in enumerate(DATES):
        for fc in FCS:
            key = (fc, day_idx)

            if key == MISSING_ROW:
                continue

            if key in SPECIAL:
                label, vec = SPECIAL[key]
                rev = revenue_for(fc, day, day_idx)

                if label == "ZERO_REVENUE":
                    rows.append({
                        "FC Name": fc, "Date": day, "Revenue": 0,
                        "Manpower Cost": ZERO_REVENUE_FIXED_COSTS["manpower_cost"],
                        "Packaging Cost": ZERO_REVENUE_FIXED_COSTS["packaging_cost"],
                        "Power & Fuel": ZERO_REVENUE_FIXED_COSTS["power_fuel"],
                        "FC Rent": ZERO_REVENUE_FIXED_COSTS["fc_rent"],
                        "Equipment Rentals": ZERO_REVENUE_FIXED_COSTS["equipment_rentals"],
                        "Overheads": ZERO_REVENUE_FIXED_COSTS["overheads"],
                    })
                    labels.append((fc, day, label, None, None))
                    continue

                amounts = {COL_MAP[k]: round(rev * v / 100) for k, v in vec.items()}
                rows.append({"FC Name": fc, "Date": day, "Revenue": rev, **amounts})
                labels.append((fc, day, label, pct_of(vec), cm2_of(vec)))
                continue

            # Default: clean/Green day, solved to land CM2% in [28.2, 30.0]
            vec = solve_margin_only_vector((70.0, 71.8))
            rev = revenue_for(fc, day, day_idx)
            amounts = {COL_MAP[k]: round(rev * v / 100) for k, v in vec.items()}
            rows.append({"FC Name": fc, "Date": day, "Revenue": rev, **amounts})
            labels.append((fc, day, "CLEAN", pct_of(vec), cm2_of(vec)))

    daily_df = pd.DataFrame(rows).sort_values(["Date", "FC Name"]).reset_index(drop=True)

    target_rows = []
    for key, (lo, hi) in RANGES.items():
        target_rows.append({"Line Item": COL_MAP[key], "Min %": lo, "Max %": hi})
    target_rows.append({"Line Item": "CM1 (% of Revenue)", "Min %": 65, "Max %": 70})
    target_rows.append({"Line Item": "CM2 (% of Revenue)", "Min %": 15, "Max %": 30})
    target_df = pd.DataFrame(target_rows)
    target_df["Notes"] = ""
    target_df.loc[target_df["Line Item"].str.startswith("CM"), "Notes"] = "±3pp tolerance before flagging"

    out_path = "sample_data/input/fc_daily_data.xlsx"
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        daily_df.to_excel(writer, sheet_name="Daily Data", index=False)
        target_df.to_excel(writer, sheet_name="Target Ranges", index=False)

    # ---- Self-check: verify every planted scenario lands in its intended zone
    print(f"Wrote {len(daily_df)} rows to {out_path}")
    print(f"FCs: {FCS}")
    print(f"Date range: {DATES[0]} to {DATES[-1]}")
    print(f"Missing row: {MISSING_ROW}")
    print()

    def color_of(cm2: float) -> str:
        if cm2 < 12:
            return "RED"
        if cm2 <= 30:
            return "GREEN" if cm2 >= 15 else "YELLOW"
        if cm2 <= 33:
            return "YELLOW"
        return "BLUE"

    counts: dict[str, int] = {"GREEN": 0, "YELLOW": 0, "RED": 0, "BLUE": 0, "ZERO_REVENUE": 0}
    print("Planted scenario verification:")
    for fc, day, label, total_pct, cm2 in labels:
        if label == "ZERO_REVENUE":
            counts["ZERO_REVENUE"] += 1
            continue
        color = color_of(cm2)
        counts[color] += 1
        if label != "CLEAN":
            print(f"  {fc} {day} [{label}]: total_cost%={total_pct:.1f} CM2%={cm2:.1f} -> {color}")

    print()
    print("Color distribution:", counts)


if __name__ == "__main__":
    main()
