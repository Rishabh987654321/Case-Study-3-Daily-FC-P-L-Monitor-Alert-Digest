# API Endpoints — FC P&L Monitor

Base URL: `http://localhost:8000/api`

## Upload & Processing

### POST /api/upload

Upload FC daily data file for processing.

**Request:** multipart/form-data

- `file` (required): CSV or Excel file (.csv, .xlsx, .xls)
- `name` (optional): Display name for this upload (e.g., "November Week 1")

**Response:** 201

```json
{
  "upload_id": "uuid",
  "status": "processing",
  "filename": "fc_daily_data.xlsx"
}
```

**Errors:**

- 400 INVALID_FILE — wrong type, too large, or missing columns
- 400 NO_DATA — file has headers but no data rows

### GET /api/upload/{id}

Get upload status and summary.

**Response:** 200

```json
{
  "id": "uuid",
  "filename": "fc_daily_data.xlsx",
  "name": "November Week 1",
  "status": "completed",
  "fc_count": 3,
  "day_count": 30,
  "anomaly_count": 12,
  "created_at": "2026-11-01T10:00:00",
  "completed_at": "2026-11-01T10:00:02"
}
```

### GET /api/uploads

List all uploads (paginated).

**Query params:** `page` (default 1), `page_size` (default 20)

**Response:** 200 — paginated list of upload summaries

### DELETE /api/upload/{id}

Delete upload and all associated data.

**Response:** 204

## P&L Data

### GET /api/upload/{id}/dashboard

Dashboard data: cross-FC daily status grid.

**Response:** 200

```json
{
  "dates": ["2026-11-01", "2026-11-02", ...],
  "fcs": ["FC-Delhi", "FC-Mumbai", "FC-Bangalore"],
  "grid": {
    "FC-Delhi": [
      {"date": "2026-11-01", "cm2_pct": 22.5, "color_code": "GREEN", "anomaly_count": 0},
      {"date": "2026-11-02", "cm2_pct": 10.1, "color_code": "RED", "anomaly_count": 3}
    ],
    ...
  }
}
```

### GET /api/upload/{id}/pnl

Full P&L data (paginated, filterable).

**Query params:**

- `fc` — filter by FC name
- `date_from`, `date_to` — date range filter
- `color` — filter by color code (RED, YELLOW, GREEN, BLUE)
- `page`, `page_size`

**Response:** 200 — paginated list of FCDayPnL records

### GET /api/upload/{id}/pnl/{fc_day_id}

Single FC-day detail with full P&L breakdown and insight.

**Response:** 200

```json
{
  "fc_name": "FC-Delhi",
  "date": "2026-11-02",
  "revenue": 150000,
  "manpower_cost": 52000,
  "packaging_cost": 12000,
  "power_fuel": 23000,
  "fc_rent": 20000,
  "equipment_rentals": 8000,
  "overheads": 12000,
  "cm1": 86000,
  "cm1_pct": 57.3,
  "cm2": 23000,
  "cm2_pct": 15.3,
  "manpower_pct": 34.7,
  "packaging_pct": 8.0,
  "power_fuel_pct": 15.3,
  "fc_rent_pct": 13.3,
  "equipment_pct": 5.3,
  "overheads_pct": 8.0,
  "color_code": "YELLOW",
  "anomalies": [...],
  "insight": "On Nov 2, FC-Delhi CM2 = 15.3%..."
}
```

## Anomalies

### GET /api/upload/{id}/anomalies

Anomaly log (paginated, filterable).

**Query params:**

- `fc` — filter by FC name
- `severity` — HIGH, MEDIUM, INFO
- `line_item` — filter by line item name
- `date_from`, `date_to`
- `page`, `page_size`

**Response:** 200 — paginated list of AnomalyLogEntry records

## Digests

### GET /api/upload/{id}/digests

All generated digests for this upload.

**Query params:**

- `fc` — filter by FC name
- `date` — filter by specific date
- `color` — filter by color code

**Response:** 200

```json
{
  "digests": [
    {
      "fc_name": "FC-Delhi",
      "date": "2026-11-02",
      "color_code": "RED",
      "summary_text": "On Nov 2, FC-Delhi CM2 = 10.1%...",
      "html_content": "<div>...</div>"
    }
  ]
}
```

### GET /api/upload/{id}/digests/{fc}/{date}

Single digest for a specific FC and date.

**Response:** 200 — DigestResponse (includes HTML for display)

## Export

### GET /api/upload/{id}/export

Download the full P&L report as Excel.

**Response:** 200 — application/vnd.openxmlformats-officedocument.spreadsheetml.sheet

### GET /api/upload/{id}/export/anomalies

Download anomaly log as CSV.

**Response:** 200 — text/csv

## System

### GET /api/health

**Response:** 200

```json
{ "status": "ok", "version": "1.0.0" }
```

### GET /api/config

**Response:** 200 — current target ranges and thresholds (read-only)

```json
{
  "targets": {
    "manpower": {"min": 20, "max": 28},
    "packaging": {"min": 5, "max": 10},
    ...
  },
  "cm1": {"min": 65, "max": 70},
  "cm2": {"min": 15, "max": 30},
  "cm_tolerance": 3,
  "max_file_mb": 50,
  "notify_channel": "file"
}
```

## Error Format

All errors return:

```json
{
  "error": {
    "code": "INVALID_FILE",
    "message": "Human-readable description"
  }
}
```

Error codes: INVALID_FILE, NO_DATA, NOT_FOUND, PROCESSING_ERROR, ALREADY_PROCESSING
