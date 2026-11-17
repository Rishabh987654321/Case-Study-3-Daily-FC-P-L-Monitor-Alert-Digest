# Data Model — FC P&L Monitor

## Database Tables

### uploads

| Column        | Type     | Notes                           |
| ------------- | -------- | ------------------------------- |
| id            | TEXT PK  | UUID                            |
| filename      | TEXT     | Original upload filename        |
| status        | TEXT     | processing / completed / failed |
| error_message | TEXT     | null unless failed              |
| fc_count      | INTEGER  | Number of distinct FCs found    |
| day_count     | INTEGER  | Number of distinct days         |
| anomaly_count | INTEGER  | Total anomalies flagged         |
| created_at    | DATETIME | Upload timestamp                |
| completed_at  | DATETIME | Processing completion           |

### fc_days

Per-FC, per-day P&L row — the core data table.

| Column            | Type     | Notes                                    |
| ----------------- | -------- | ---------------------------------------- |
| id                | TEXT PK  | UUID                                     |
| upload_id         | TEXT FK  | → uploads.id                             |
| fc_name           | TEXT     | Fulfilment centre name                   |
| date              | DATE     | The business day                         |
| revenue           | FLOAT    |                                          |
| manpower_cost     | FLOAT    |                                          |
| packaging_cost    | FLOAT    |                                          |
| power_fuel        | FLOAT    | Power & Fuel                             |
| fc_rent           | FLOAT    |                                          |
| equipment_rentals | FLOAT    |                                          |
| overheads         | FLOAT    |                                          |
| cm1               | FLOAT    | Computed: Revenue - Manpower - Packaging |
| cm1_pct           | FLOAT    | CM1 as % of revenue                      |
| cm2               | FLOAT    | Computed: CM1 - remaining costs          |
| cm2_pct           | FLOAT    | CM2 as % of revenue                      |
| manpower_pct      | FLOAT    | Manpower as % of revenue                 |
| packaging_pct     | FLOAT    |                                          |
| power_fuel_pct    | FLOAT    |                                          |
| fc_rent_pct       | FLOAT    |                                          |
| equipment_pct     | FLOAT    |                                          |
| overheads_pct     | FLOAT    |                                          |
| color_code        | TEXT     | RED / YELLOW / GREEN / BLUE              |
| insight           | TEXT     | Plain-language insight for this FC-day   |
| created_at        | DATETIME |                                          |

### anomalies

| Column     | Type     | Notes                                                       |
| ---------- | -------- | ----------------------------------------------------------- |
| id         | TEXT PK  | UUID                                                        |
| upload_id  | TEXT FK  | → uploads.id                                                |
| fc_day_id  | TEXT FK  | → fc_days.id                                                |
| fc_name    | TEXT     | Denormalized for query convenience                          |
| date       | DATE     | Denormalized                                                |
| line_item  | TEXT     | e.g., "Manpower Cost", "CM2"                                |
| actual_pct | FLOAT    | The actual % of revenue                                     |
| target_min | FLOAT    |                                                             |
| target_max | FLOAT    |                                                             |
| deviation  | FLOAT    | How far outside range (signed)                              |
| status     | TEXT     | BREACH_LOW / BREACH_HIGH / ZERO_REVENUE                     |
| severity   | TEXT     | HIGH (margin breach) / MEDIUM (line item) / INFO (zero rev) |
| created_at | DATETIME |                                                             |

### digests

| Column        | Type     | Notes                              |
| ------------- | -------- | ---------------------------------- |
| id            | TEXT PK  | UUID                               |
| upload_id     | TEXT FK  | → uploads.id                       |
| fc_name       | TEXT     |                                    |
| date          | DATE     |                                    |
| color_code    | TEXT     | RED / YELLOW / GREEN / BLUE        |
| summary_text  | TEXT     | The plain-language digest          |
| html_content  | TEXT     | Full HTML digest for email/display |
| delivered_via | TEXT     | file / email / webhook             |
| delivered_at  | DATETIME | null if not yet delivered          |
| created_at    | DATETIME |                                    |

## Pydantic Models

### Input Models

```python
class FCDayRecord(BaseModel):
    """Raw parsed row from input file."""
    fc_name: str
    date: date
    revenue: float
    manpower_cost: float
    packaging_cost: float
    power_fuel: float
    fc_rent: float
    equipment_rentals: float
    overheads: float
```

### Computed Models

```python
class FCDayPnL(BaseModel):
    """Fully computed P&L for one FC-day."""
    fc_name: str
    date: date
    revenue: float
    # Raw costs
    manpower_cost: float
    packaging_cost: float
    power_fuel: float
    fc_rent: float
    equipment_rentals: float
    overheads: float
    # Computed
    cm1: float
    cm1_pct: float
    cm2: float
    cm2_pct: float
    manpower_pct: float
    packaging_pct: float
    power_fuel_pct: float
    fc_rent_pct: float
    equipment_pct: float
    overheads_pct: float
    # Detection results
    color_code: str  # RED/YELLOW/GREEN/BLUE
    anomalies: list[Anomaly]
    insight: str

class Anomaly(BaseModel):
    line_item: str
    actual_pct: float
    target_min: float
    target_max: float
    deviation: float
    status: str  # BREACH_LOW / BREACH_HIGH / ZERO_REVENUE
    severity: str  # HIGH / MEDIUM / INFO
```

### API Response Models

```python
class UploadSummary(BaseModel):
    id: str
    filename: str
    status: str
    fc_count: int
    day_count: int
    anomaly_count: int
    created_at: datetime
    completed_at: datetime | None

class FCDaySummary(BaseModel):
    """Lightweight version for dashboard grid."""
    fc_name: str
    date: date
    cm2_pct: float
    color_code: str
    anomaly_count: int

class DashboardData(BaseModel):
    """Cross-FC daily status grid."""
    dates: list[date]
    fcs: list[str]
    grid: list[list[FCDaySummary]]  # [fc_index][date_index]

class AnomalyLogEntry(BaseModel):
    date: date
    fc_name: str
    line_item: str
    actual_pct: float
    target_range: str  # "20-28%"
    status: str
    severity: str

class DigestResponse(BaseModel):
    fc_name: str
    date: date
    color_code: str
    summary_text: str
    html_content: str
    generation_mode: str  # "llm" or "rule"
```

## Export Spreadsheet

### Sheet 1: "P&L Details"

All fc_days columns, one row per FC per day. Sorted by date, then FC name.

- Header row: bold, frozen
- Color-code column: cell fill matching RED/YELLOW/GREEN/BLUE
- Anomalous cost cells: orange background

### Sheet 2: "Anomaly Log"

All anomalies, sorted by date, then FC, then severity.
Columns: Date, FC, Line Item, Actual %, Target Min %, Target Max %, Deviation, Status, Severity

### Sheet 3: "FC Summary"

Per-FC aggregates: FC Name, Days Analyzed, Green Days, Yellow Days, Red Days, Blue Days, Avg CM2%, Total Anomalies

### Sheet 4: "Digests"

Per-FC per-day: Date, FC, Color, Insight Text

## .env.example

```
# Server
PORT=8000
HOST=0.0.0.0

# Database
DATABASE_URL=sqlite:///./data/pnl_monitor.db

# File uploads
MAX_FILE_MB=50
UPLOAD_DIR=./data/uploads

# Target ranges (% of revenue)
TARGET_MANPOWER_MIN=20
TARGET_MANPOWER_MAX=28
TARGET_PACKAGING_MIN=5
TARGET_PACKAGING_MAX=10
TARGET_POWER_FUEL_MIN=3
TARGET_POWER_FUEL_MAX=7
TARGET_RENT_MIN=8
TARGET_RENT_MAX=15
TARGET_EQUIPMENT_MIN=2
TARGET_EQUIPMENT_MAX=5
TARGET_OVERHEADS_MIN=3
TARGET_OVERHEADS_MAX=7

# Margin targets
TARGET_CM1_MIN=65
TARGET_CM1_MAX=70
TARGET_CM2_MIN=15
TARGET_CM2_MAX=30
CM_TOLERANCE=3

# LLM (Ollama — local, free)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_TIMEOUT=10
INSIGHT_MODE=auto  # auto=LLM with rule fallback, llm=LLM only, rule=templates only

# Notifications
NOTIFY_CHANNEL=file
# For email: NOTIFY_CHANNEL=email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
DIGEST_RECIPIENTS=

# For webhook: NOTIFY_CHANNEL=webhook
WEBHOOK_URL=
```
