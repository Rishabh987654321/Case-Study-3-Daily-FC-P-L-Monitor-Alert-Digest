"""Ingest Agent — parse CSV/Excel into normalized FCDayRecord list.

Column headers are matched flexibly (case/whitespace-insensitive, several
aliases per field) so the system works on unseen files that don't use our
exact sample-data column names.
"""

import csv
import re
from datetime import date as date_type
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.errors import IngestError
from app.types import FCDayRecord

REQUIRED_FIELDS = {"fc_name", "date", "revenue"}

ALIASES: dict[str, list[str]] = {
    "fc_name": ["fc", "fc name", "centre", "center", "fulfilment centre",
                "fulfillment centre", "fulfilment center", "fulfillment center"],
    "date": ["date", "day"],
    "revenue": ["revenue", "total revenue"],
    "manpower_cost": ["manpower", "manpower cost", "labour", "labor"],
    "packaging_cost": ["packaging", "packaging cost", "packing"],
    "power_fuel": ["power", "power & fuel", "power and fuel", "electricity"],
    "fc_rent": ["rent", "fc rent", "warehouse rent"],
    "equipment_rentals": ["equipment", "equipment rentals", "equipment rental"],
    "overheads": ["overheads", "overhead", "other", "other costs"],
}

COST_FIELDS = [f for f in ALIASES if f not in REQUIRED_FIELDS]

FIELD_LABELS = {
    "fc_name": "FC name", "date": "date", "revenue": "revenue",
    "manpower_cost": "manpower cost", "packaging_cost": "packaging cost",
    "power_fuel": "power & fuel", "fc_rent": "FC rent",
    "equipment_rentals": "equipment rentals", "overheads": "overheads",
}

# Tried in priority order. ISO and named-month formats are unambiguous and
# always tried first; "%d/%m/%Y" (day-first) is tried before "%m/%d/%Y"
# because this system's primary audience writes dates day-first (India) —
# genuinely ambiguous slash-dates ("05/11/2026") are resolved that way.
_DATE_FORMATS = [
    "%Y-%m-%d", "%Y/%m/%d",
    "%d-%b-%Y", "%d %b %Y", "%d-%B-%Y", "%d %B %Y",
    "%d/%m/%Y", "%d-%m-%Y",
    "%m/%d/%Y", "%m-%d-%Y",
]


def _parse_date_value(raw: object) -> date_type | None:
    """Parse a single date cell. Handles native datetime/Timestamp values
    (the common case for Excel) and a prioritized list of string formats
    (for CSV / text cells) without pandas' column-wide dayfirst ambiguity."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date_type):
        return raw
    if pd.isna(raw):
        return None

    text = str(raw).strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    parsed = pd.to_datetime(text, errors="coerce")
    return None if pd.isna(parsed) else parsed.date()


def _normalize(header: str) -> str:
    return re.sub(r"\s+", " ", str(header).strip().lower())


def _build_column_map(columns: list[str]) -> dict[str, str]:
    """Map canonical field name -> actual dataframe column name."""
    colmap: dict[str, str] = {}
    for col in columns:
        normalized = _normalize(col)
        for field, aliases in ALIASES.items():
            if field in colmap:
                continue
            if normalized in aliases:
                colmap[field] = col
                break
    return colmap


class IngestAgent:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def run(self, file_path: str) -> list[FCDayRecord]:
        self.warnings = []
        path = Path(file_path)
        if not path.exists():
            raise IngestError(f"File not found: {file_path}")

        df = self._read_dataframe(path)

        if df is None or df.shape[1] == 0:
            raise IngestError("File is empty or unreadable — no columns found.")

        colmap = _build_column_map(list(df.columns))
        missing_required = REQUIRED_FIELDS - colmap.keys()
        if missing_required:
            labels = ", ".join(FIELD_LABELS[f] for f in sorted(missing_required))
            raise IngestError(f"Could not find required column(s): {labels}")

        for field in COST_FIELDS:
            if field not in colmap:
                self.warnings.append(
                    f"Column for {FIELD_LABELS[field]} not found; defaulting to 0.0 for all rows."
                )

        if df.shape[0] == 0:
            self.warnings.append("File has headers but no data rows.")
            return []

        records = self._parse_rows(df, colmap)

        if not records:
            self.warnings.append("No valid data rows remained after validation.")

        self._warn_on_duplicates(records)

        return sorted(records, key=lambda r: (r.date, r.fc_name))

    def _warn_on_duplicates(self, records: list[FCDayRecord]) -> None:
        seen: dict[tuple[str, date_type], int] = {}
        for r in records:
            key = (r.fc_name, r.date)
            seen[key] = seen.get(key, 0) + 1
        duplicates = {k: v for k, v in seen.items() if v > 1}
        if duplicates:
            example_fc, example_date = next(iter(duplicates))
            self.warnings.append(
                f"{len(duplicates)} duplicate (FC, date) pair(s) found (e.g. {example_fc} on "
                f"{example_date}) — all rows kept; the dashboard grid will show only the last one "
                "per FC-day, but every row is still in the full P&L list."
            )

    def _read_dataframe(self, path: Path) -> pd.DataFrame | None:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            try:
                return pd.read_csv(path, sep=None, engine="python")
            except (pd.errors.EmptyDataError, csv.Error):
                raise IngestError("CSV file is empty.") from None
            except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as exc:
                raise IngestError(f"Could not parse CSV file: {exc}") from None
        if suffix in (".xlsx", ".xls"):
            return self._read_excel(path)
        raise IngestError(f"Unsupported file type: {suffix}. Use .csv, .xlsx, or .xls.")

    def _read_excel(self, path: Path) -> pd.DataFrame:
        try:
            xls = pd.ExcelFile(path)
            sheet_names = xls.sheet_names
            if not sheet_names:
                raise IngestError("Excel file has no sheets.")

            # Prefer a sheet explicitly named "Daily Data"
            for name in sheet_names:
                if _normalize(name) == "daily data":
                    return pd.read_excel(xls, sheet_name=name)

            # Otherwise use the first sheet that has at least one data row
            first_non_empty = None
            for name in sheet_names:
                sheet_df = pd.read_excel(xls, sheet_name=name)
                if first_non_empty is None:
                    first_non_empty = sheet_df
                if sheet_df.shape[0] > 0:
                    return sheet_df
            return first_non_empty
        except IngestError:
            raise
        except Exception as exc:
            raise IngestError(
                f"Could not read Excel file (is it actually .xlsx/.xls format?): {exc}"
            ) from None

    def _parse_rows(self, df: pd.DataFrame, colmap: dict[str, str]) -> list[FCDayRecord]:
        work = pd.DataFrame()
        work["fc_name"] = df[colmap["fc_name"]]
        work["date_raw"] = df[colmap["date"]]
        work["revenue"] = pd.to_numeric(df[colmap["revenue"]], errors="coerce")
        for field in COST_FIELDS:
            work[field] = df[colmap[field]] if field in colmap else 0.0

        records: list[FCDayRecord] = []
        skipped_total_rows = 0
        skipped_bad_date = 0
        skipped_missing_revenue = 0
        skipped_bad_cost: dict[str, int] = {}
        negative_counts: dict[str, int] = {}
        defaulted_counts: dict[str, int] = {}

        for _, row in work.iterrows():
            fc_name = row["fc_name"]
            fc_name_str = "" if pd.isna(fc_name) else str(fc_name).strip()

            if not fc_name_str or "total" in fc_name_str.lower():
                skipped_total_rows += 1
                continue

            parsed_date = _parse_date_value(row["date_raw"])
            if parsed_date is None:
                skipped_bad_date += 1
                continue

            if pd.isna(row["revenue"]):
                skipped_missing_revenue += 1
                continue
            revenue = float(row["revenue"])
            if revenue < 0:
                negative_counts["revenue"] = negative_counts.get("revenue", 0) + 1

            costs: dict[str, float] = {}
            row_has_bad_cost = False
            for field in COST_FIELDS:
                raw = row[field]
                if field not in colmap:
                    costs[field] = 0.0
                    continue
                if pd.isna(raw):
                    defaulted_counts[field] = defaulted_counts.get(field, 0) + 1
                    costs[field] = 0.0
                    continue
                try:
                    val = float(raw)
                except (TypeError, ValueError):
                    skipped_bad_cost[field] = skipped_bad_cost.get(field, 0) + 1
                    row_has_bad_cost = True
                    break
                if val < 0:
                    negative_counts[field] = negative_counts.get(field, 0) + 1
                costs[field] = val

            if row_has_bad_cost:
                continue

            records.append(FCDayRecord(
                fc_name=fc_name_str,
                date=parsed_date,
                revenue=revenue,
                **costs,
            ))

        if skipped_total_rows:
            self.warnings.append(f"Skipped {skipped_total_rows} summary/total row(s).")
        if skipped_bad_date:
            self.warnings.append(f"Skipped {skipped_bad_date} row(s) with missing/unparsable date.")
        if skipped_missing_revenue:
            self.warnings.append(f"Skipped {skipped_missing_revenue} row(s) with missing/unparsable revenue.")
        for field, count in skipped_bad_cost.items():
            self.warnings.append(
                f"Skipped {count} row(s) with non-numeric {FIELD_LABELS[field]} values."
            )
        for field, count in defaulted_counts.items():
            self.warnings.append(
                f"{FIELD_LABELS[field]}: {count} row(s) had a blank value, defaulted to 0.0."
            )
        for field, count in negative_counts.items():
            self.warnings.append(
                f"{FIELD_LABELS[field]}: {count} row(s) had negative values — kept as-is (may be valid credits)."
            )

        return records
