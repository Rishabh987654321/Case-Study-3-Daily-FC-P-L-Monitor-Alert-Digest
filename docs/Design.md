# UI Design — FC P&L Monitor

## Screens

### 1. Upload Page (`/upload`)

Simple file upload for FC daily data.

**Layout:**

- Single drop zone: "Drop your FC daily data file (CSV or Excel)"
  - Accepts .csv, .xlsx, .xls
  - Shows filename + size after selection
- Optional text field: "Upload name (e.g., November Week 1)"
- "Analyze Data" button (disabled until file selected)
- On upload: navigate to dashboard

**Error states:**

- Wrong file type → inline error on drop zone
- File too large → inline error
- Server unreachable → toast error + retry button

### 2. Dashboard Page (`/dashboard/{upload_id}`)

The central view — color-coded grid of all FCs across all days.

**Header:**

- Upload name + file info
- Date range: "{earliest} to {latest}"
- Quick stats: X FCs, Y days, Z anomalies
- Action buttons: Download Report, Delete

**Processing state:**

- While status=processing: spinner + "Analyzing {fc_count} centres..."
- Poll every 2 seconds

**A. Color Grid (main feature)**
A matrix/heatmap: rows = FCs, columns = dates.
Each cell is colored by the day's color code:

- 🔴 Red: #EF4444 (bg-red-500)
- 🟡 Yellow: #F59E0B (bg-amber-500)
- 🟢 Green: #22C55E (bg-green-500)
- 🔵 Blue: #3B82F6 (bg-blue-500)

Cell shows CM2% value. Click cell → navigate to FC detail page for that day.

Hover tooltip: "{FC} — {date}: CM2 = {pct}%, {n} anomalies"

**B. Summary Cards**
Below the grid, four cards:

- Total Red days (count + %)
- Total Yellow days
- Total Green days
- Total Blue days

**C. Top Anomalies**
"Top 5 Most Critical" — sorted by severity then impact:

- FC name, date, issue summary, color badge

**D. Filters**

- Date range picker
- FC dropdown (multi-select)
- Color filter (checkboxes)

### 3. FC Detail Page (`/dashboard/{upload_id}/fc/{fc_name}`)

Drill-down for one FC across all days.

**Header:**

- FC name + date range
- Overall stats: avg CM2%, green/yellow/red day counts

**A. Trend Charts (Recharts)**
Two line charts side by side:

1. **Margin Trend**: CM1% and CM2% over time, with target range bands shown as shaded areas
2. **Cost Breakdown Trend**: stacked area or multi-line showing each cost line % over time

Charts have:

- Target range as shaded band (light green for OK zone)
- Threshold lines (dashed red for CM2 12%, dashed blue for CM2 33%)
- Tooltips showing exact values on hover

**B. Daily P&L Table**
Columns: Date, Revenue, Manpower%, Packaging%, Power%, Rent%, Equipment%, Overheads%, CM1%, CM2%, Color, Anomalies

- Color badge in the Color column
- Anomalous cells highlighted (orange text or background)
- Click row → expand to show insight text + anomaly details

**C. Anomaly Log**
Filtered to this FC. Table: Date, Line Item, Actual%, Target Range, Status, Severity

- Sortable by any column
- Severity badges (HIGH=red, MEDIUM=orange, INFO=gray)

**D. Digest History**
List of generated digests for this FC, each expandable to show the HTML content.

### 4. History Page (`/history`)

- List all uploads: name, date, FC count, day count, anomaly count, status
- Click → navigate to dashboard
- Delete button with confirmation

## Shared Components

### FCCard

Small card for the dashboard grid cell. Shows FC name, CM2%, color-coded background.

### ColorBadge

Inline badge with color circle + label (Red/Yellow/Green/Blue).

### AnomalyBadge

Severity indicator: HIGH (red), MEDIUM (orange), INFO (gray).

### InsightBox

Expandable panel showing the plain-language insight text.

## Navigation

- Top nav: "FC P&L Monitor" title + Upload / Dashboard / History links
- Dashboard is the primary working view
- Breadcrumbs on FC Detail: Dashboard > {FC Name}

## Routing

- `/` → redirect to `/upload`
- `/upload` → UploadPage
- `/dashboard/:id` → DashboardPage
- `/dashboard/:id/fc/:name` → FCDetailPage
- `/history` → HistoryPage

## Responsive

- Dashboard grid scrolls horizontally on narrow screens
- Charts resize responsively
- Table stacks into cards on mobile (nice-to-have, not required)
