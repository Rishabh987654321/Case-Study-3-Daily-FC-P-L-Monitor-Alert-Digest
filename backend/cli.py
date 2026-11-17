"""CLI tool to run the full pipeline on a file and print results.

Usage: python -m cli sample_data/input/fc_daily_data.xlsx
"""

import asyncio
import json
import sys

import pandas as pd

from app.config import PROJECT_ROOT, get_settings
from app.pipeline.orchestrator import run_pipeline

OUTPUT_DIR = PROJECT_ROOT / "sample_data" / "output"


def _impact(anomaly, pnl_lookup: dict) -> float:
    revenue = pnl_lookup.get((anomaly.fc_name, anomaly.date), 0.0)
    return abs(anomaly.deviation) * revenue


_SEVERITY_RANK = {"HIGH": 0, "MEDIUM": 1, "INFO": 2}


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m cli <path-to-file.csv|.xlsx>")
        sys.exit(1)

    file_path = sys.argv[1]
    settings = get_settings()

    result = asyncio.run(
        run_pipeline(file_path, settings, digests_output_dir=OUTPUT_DIR / "digests")
    )

    pnl_data = result.pnl_data
    fcs = sorted({p.fc_name for p in pnl_data})
    days = sorted({p.date for p in pnl_data})

    print("=" * 60)
    print("PIPELINE SUMMARY")
    print("=" * 60)
    print(f"FCs: {len(fcs)} ({', '.join(fcs)})")
    print(f"Days: {len(days)} ({days[0]} to {days[-1]})" if days else "Days: 0")
    print(f"Records: {len(result.records)}")
    print(f"Anomalies: {len(result.anomalies)}")
    if result.ingest_warnings:
        print(f"Ingest warnings: {len(result.ingest_warnings)}")
        for w in result.ingest_warnings:
            print(f"  - {w}")

    print()
    print("COLOR DISTRIBUTION")
    counts = {"GREEN": 0, "YELLOW": 0, "RED": 0, "BLUE": 0}
    for p in pnl_data:
        if p.color_code:
            counts[p.color_code.value] += 1
    print(f"  Green:  {counts['GREEN']}")
    print(f"  Yellow: {counts['YELLOW']}")
    print(f"  Red:    {counts['RED']}")
    print(f"  Blue:   {counts['BLUE']}")

    print()
    print("INSIGHT GENERATION MODE")
    print(f"  LLM:  {result.mode_counts.get('llm', 0)}")
    print(f"  Rule: {result.mode_counts.get('rule', 0)}")

    print()
    print("TOP 5 ANOMALIES")
    pnl_lookup = {(p.fc_name, str(p.date)): p.revenue for p in pnl_data}
    ranked = sorted(
        result.anomalies,
        key=lambda a: (_SEVERITY_RANK.get(a.severity, 9), -_impact(a, pnl_lookup)),
    )
    for a in ranked[:5]:
        print(f"  [{a.severity}] {a.fc_name} {a.date} — {a.line_item}: "
              f"{a.actual_pct}% (target {a.target_min}-{a.target_max}%, status {a.status})")

    print()
    print("SAMPLE DIGESTS")
    shown = 0
    for d in result.digests:
        if d.anomalies and shown < 3:
            print(f"--- {d.fc_name} {d.date} [{d.color_code.value}] (mode={d.generation_mode}) ---")
            print(d.insight_text)
            print()
            shown += 1

    print(f"Timings: {result.timings}")
    print(f"Delivery results: {len(result.delivery_results)} file(s) written")
    if result.notify_warnings:
        for w in result.notify_warnings:
            print(f"  Notify warning: {w}")

    _save_outputs(result, pnl_data)
    print(f"\nSaved pnl_report.csv and anomaly_log.json to {OUTPUT_DIR}")


def _save_outputs(result, pnl_data) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for p in pnl_data:
        rows.append({
            "fc_name": p.fc_name, "date": str(p.date), "revenue": p.revenue,
            "manpower_cost": p.manpower_cost, "packaging_cost": p.packaging_cost,
            "power_fuel": p.power_fuel, "fc_rent": p.fc_rent,
            "equipment_rentals": p.equipment_rentals, "overheads": p.overheads,
            "cm1": p.cm1, "cm1_pct": p.cm1_pct, "cm2": p.cm2, "cm2_pct": p.cm2_pct,
            "manpower_pct": p.manpower_pct, "packaging_pct": p.packaging_pct,
            "power_fuel_pct": p.power_fuel_pct, "fc_rent_pct": p.fc_rent_pct,
            "equipment_pct": p.equipment_pct, "overheads_pct": p.overheads_pct,
            "color_code": p.color_code.value if p.color_code else None,
            "anomaly_count": len(p.anomalies),
        })
    pd.DataFrame(rows).sort_values(["date", "fc_name"]).to_csv(
        OUTPUT_DIR / "pnl_report.csv", index=False
    )

    anomaly_rows = [
        {
            "fc_name": a.fc_name, "date": a.date, "line_item": a.line_item,
            "actual_pct": a.actual_pct, "target_min": a.target_min, "target_max": a.target_max,
            "deviation": a.deviation, "status": a.status, "severity": a.severity,
        }
        for a in result.anomalies
    ]
    (OUTPUT_DIR / "anomaly_log.json").write_text(json.dumps(anomaly_rows, indent=2))


if __name__ == "__main__":
    main()
