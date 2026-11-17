"""Excel report writer — 4-sheet workbook matching docs/data_model.md "Export Spreadsheet".

Deviates slightly from the literal `write_pnl_report(fc_days, anomalies, output_path)`
signature in phase2-prompt.md: `anomalies` here is the orchestrator's flattened
anomaly list (fc_name/date denormalized, matching the Anomaly Log sheet directly),
and a `digests` list is added, since the "Digests" sheet needs insight text which
lives on FCDayDigest, not on FCDayPnL or the pipeline Anomaly model.
"""

from collections import defaultdict

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from app.pipeline.orchestrator import FlatAnomaly
from app.types import FCDayDigest, FCDayPnL

_COLOR_FILL = {
    "RED": PatternFill(start_color="EF4444", end_color="EF4444", fill_type="solid"),
    "YELLOW": PatternFill(start_color="F59E0B", end_color="F59E0B", fill_type="solid"),
    "GREEN": PatternFill(start_color="22C55E", end_color="22C55E", fill_type="solid"),
    "BLUE": PatternFill(start_color="3B82F6", end_color="3B82F6", fill_type="solid"),
}
_ANOMALY_FILL = PatternFill(start_color="FDBA74", end_color="FDBA74", fill_type="solid")
_HEADER_FONT = Font(bold=True)

_PNL_COLUMNS: list[tuple[str, str, str | None]] = [
    ("Date", "date", None),
    ("FC", "fc_name", None),
    ("Revenue", "revenue", None),
    ("Manpower Cost", "manpower_cost", None),
    ("Manpower %", "manpower_pct", "Manpower Cost"),
    ("Packaging Cost", "packaging_cost", None),
    ("Packaging %", "packaging_pct", "Packaging Cost"),
    ("Power & Fuel", "power_fuel", None),
    ("Power & Fuel %", "power_fuel_pct", "Power & Fuel"),
    ("FC Rent", "fc_rent", None),
    ("FC Rent %", "fc_rent_pct", "FC Rent"),
    ("Equipment Rentals", "equipment_rentals", None),
    ("Equipment %", "equipment_pct", "Equipment Rentals"),
    ("Overheads", "overheads", None),
    ("Overheads %", "overheads_pct", "Overheads"),
    ("CM1", "cm1", None),
    ("CM1 %", "cm1_pct", "CM1"),
    ("CM2", "cm2", None),
    ("CM2 %", "cm2_pct", "CM2"),
    ("Color Code", "color_code", None),
]

_SEVERITY_RANK = {"HIGH": 0, "MEDIUM": 1, "INFO": 2}


def _autosize(ws: Worksheet) -> None:
    for col_cells in ws.columns:
        length = max((len(str(c.value)) for c in col_cells if c.value is not None), default=8)
        ws.column_dimensions[get_column_letter(col_cells[0].column)].width = min(length + 2, 40)


def _write_pnl_details(wb: Workbook, fc_days: list[FCDayPnL]) -> None:
    ws = wb.create_sheet("P&L Details")
    ws.append([label for label, _, _ in _PNL_COLUMNS])
    for cell in ws[1]:
        cell.font = _HEADER_FONT
    ws.freeze_panes = "A2"

    anomaly_items: dict[tuple[str, str], set[str]] = defaultdict(set)
    for p in fc_days:
        for a in p.anomalies:
            anomaly_items[(p.fc_name, str(p.date))].add(a.line_item)

    for p in sorted(fc_days, key=lambda p: (p.date, p.fc_name)):
        row = []
        for label, attr, _ in _PNL_COLUMNS:
            value = getattr(p, attr)
            row.append(value.value if hasattr(value, "value") else value)
        ws.append(row)

        row_idx = ws.max_row
        color = p.color_code.value if p.color_code else None
        color_col = next(i for i, (label, _, _) in enumerate(_PNL_COLUMNS, start=1) if label == "Color Code")
        if color in _COLOR_FILL:
            ws.cell(row=row_idx, column=color_col).fill = _COLOR_FILL[color]

        flagged = anomaly_items.get((p.fc_name, str(p.date)), set())
        for col_idx, (label, _, line_item) in enumerate(_PNL_COLUMNS, start=1):
            if line_item and line_item in flagged:
                ws.cell(row=row_idx, column=col_idx).fill = _ANOMALY_FILL

    _autosize(ws)


def _target_range_str(a: FlatAnomaly) -> str:
    return f"{a.target_min}-{a.target_max}%"


def _write_anomaly_log(wb: Workbook, anomalies: list[FlatAnomaly]) -> None:
    ws = wb.create_sheet("Anomaly Log")
    headers = ["Date", "FC", "Line Item", "Actual %", "Target Min %", "Target Max %",
               "Deviation", "Status", "Severity"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = _HEADER_FONT
    ws.freeze_panes = "A2"

    ordered = sorted(anomalies, key=lambda a: (a.date, a.fc_name, _SEVERITY_RANK.get(a.severity, 9)))
    for a in ordered:
        ws.append([a.date, a.fc_name, a.line_item, a.actual_pct, a.target_min,
                   a.target_max, a.deviation, a.status, a.severity])
    _autosize(ws)


def _write_fc_summary(wb: Workbook, fc_days: list[FCDayPnL]) -> None:
    ws = wb.create_sheet("FC Summary")
    headers = ["FC Name", "Days Analyzed", "Green Days", "Yellow Days", "Red Days",
               "Blue Days", "Avg CM1%", "Avg CM2%", "Total Anomalies"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = _HEADER_FONT
    ws.freeze_panes = "A2"

    by_fc: dict[str, list[FCDayPnL]] = defaultdict(list)
    for p in fc_days:
        by_fc[p.fc_name].append(p)

    for fc_name in sorted(by_fc):
        rows = by_fc[fc_name]
        counts = {"GREEN": 0, "YELLOW": 0, "RED": 0, "BLUE": 0}
        for p in rows:
            if p.color_code:
                counts[p.color_code.value] += 1
        avg_cm1 = round(sum(p.cm1_pct for p in rows) / len(rows), 1) if rows else 0.0
        avg_cm2 = round(sum(p.cm2_pct for p in rows) / len(rows), 1) if rows else 0.0
        total_anomalies = sum(len(p.anomalies) for p in rows)
        ws.append([fc_name, len(rows), counts["GREEN"], counts["YELLOW"], counts["RED"],
                   counts["BLUE"], avg_cm1, avg_cm2, total_anomalies])
    _autosize(ws)


def _write_digests(wb: Workbook, digests: list[FCDayDigest]) -> None:
    ws = wb.create_sheet("Digests")
    ws.append(["Date", "FC", "Color", "Insight Text"])
    for cell in ws[1]:
        cell.font = _HEADER_FONT
    ws.freeze_panes = "A2"

    for d in sorted(digests, key=lambda d: (d.date, d.fc_name)):
        ws.append([d.date, d.fc_name, d.color_code.value, d.insight_text])
    ws.column_dimensions["D"].width = 80
    ws.column_dimensions["D"].alignment = Alignment(wrap_text=True)
    _autosize_except(ws, skip={"D"})


def _autosize_except(ws: Worksheet, skip: set[str]) -> None:
    for col_cells in ws.columns:
        col_letter = get_column_letter(col_cells[0].column)
        if col_letter in skip:
            continue
        length = max((len(str(c.value)) for c in col_cells if c.value is not None), default=8)
        ws.column_dimensions[col_letter].width = min(length + 2, 40)


def write_pnl_report(
    fc_days: list[FCDayPnL],
    anomalies: list[FlatAnomaly],
    digests: list[FCDayDigest],
    output_path: str,
) -> None:
    wb = Workbook()
    wb.remove(wb.active)

    _write_pnl_details(wb, fc_days)
    _write_anomaly_log(wb, anomalies)
    _write_fc_summary(wb, fc_days)
    _write_digests(wb, digests)

    wb.save(output_path)
