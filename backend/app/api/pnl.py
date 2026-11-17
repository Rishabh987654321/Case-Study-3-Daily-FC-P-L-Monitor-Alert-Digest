"""P&L data endpoints: dashboard grid, P&L rows, anomalies, digests, export."""

import csv
import io
from collections import defaultdict
from datetime import date as date_type

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import NotFoundError
from app.models import AnomalyRow, DigestRow, FCDay, Upload
from app.schemas import (
    AnomalyInline,
    AnomalyLogEntry,
    DashboardData,
    DigestResponse,
    FCDayDetail,
    FCDaySummary,
    PaginatedResponse,
)
from app.services import storage

router = APIRouter(tags=["pnl"])


def _get_upload_or_404(upload_id: str, db: Session) -> Upload:
    upload = db.get(Upload, upload_id)
    if upload is None:
        raise NotFoundError(f"Upload {upload_id} not found.")
    return upload


def _to_detail(r: FCDay, anomalies: list[AnomalyRow]) -> FCDayDetail:
    return FCDayDetail(
        id=r.id, fc_name=r.fc_name, date=r.date, revenue=r.revenue,
        manpower_cost=r.manpower_cost, packaging_cost=r.packaging_cost, power_fuel=r.power_fuel,
        fc_rent=r.fc_rent, equipment_rentals=r.equipment_rentals, overheads=r.overheads,
        cm1=r.cm1, cm1_pct=r.cm1_pct, cm2=r.cm2, cm2_pct=r.cm2_pct,
        manpower_pct=r.manpower_pct, packaging_pct=r.packaging_pct, power_fuel_pct=r.power_fuel_pct,
        fc_rent_pct=r.fc_rent_pct, equipment_pct=r.equipment_pct, overheads_pct=r.overheads_pct,
        color_code=r.color_code,
        anomalies=[AnomalyInline.model_validate(a) for a in anomalies],
        insight=r.insight,
    )


@router.get("/upload/{upload_id}/dashboard", response_model=DashboardData)
def get_dashboard(upload_id: str, db: Session = Depends(get_db)) -> DashboardData:
    _get_upload_or_404(upload_id, db)
    rows = db.query(FCDay).filter(FCDay.upload_id == upload_id).order_by(FCDay.date, FCDay.fc_name).all()

    anomaly_counts = dict(
        db.query(AnomalyRow.fc_day_id, func.count(AnomalyRow.id))
        .filter(AnomalyRow.upload_id == upload_id)
        .group_by(AnomalyRow.fc_day_id)
        .all()
    )

    dates = sorted({r.date for r in rows})
    fcs = sorted({r.fc_name for r in rows})
    by_fc_date = {(r.fc_name, r.date): r for r in rows}

    grid: dict[str, list[FCDaySummary]] = {fc: [] for fc in fcs}
    for fc in fcs:
        for d in dates:
            r = by_fc_date.get((fc, d))
            if r is not None:
                grid[fc].append(FCDaySummary(
                    fc_name=fc, date=d, cm2_pct=r.cm2_pct, color_code=r.color_code,
                    anomaly_count=anomaly_counts.get(r.id, 0),
                ))
    return DashboardData(dates=dates, fcs=fcs, grid=grid)


@router.get("/upload/{upload_id}/pnl", response_model=PaginatedResponse[FCDayDetail])
def list_pnl(
    upload_id: str,
    fc: str | None = None,
    date_from: date_type | None = None,
    date_to: date_type | None = None,
    color: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
) -> PaginatedResponse:
    _get_upload_or_404(upload_id, db)
    q = db.query(FCDay).filter(FCDay.upload_id == upload_id)
    if fc:
        q = q.filter(FCDay.fc_name == fc)
    if date_from:
        q = q.filter(FCDay.date >= date_from)
    if date_to:
        q = q.filter(FCDay.date <= date_to)
    if color:
        q = q.filter(FCDay.color_code == color.upper())

    total = q.count()
    rows = q.order_by(FCDay.date, FCDay.fc_name).offset((page - 1) * page_size).limit(page_size).all()

    anomalies_by_day: dict[str, list[AnomalyRow]] = defaultdict(list)
    day_ids = [r.id for r in rows]
    if day_ids:
        for a in db.query(AnomalyRow).filter(AnomalyRow.fc_day_id.in_(day_ids)).all():
            anomalies_by_day[a.fc_day_id].append(a)

    items = [_to_detail(r, anomalies_by_day.get(r.id, [])) for r in rows]
    total_pages = max(1, (total + page_size - 1) // page_size)
    return PaginatedResponse(items=items, page=page, page_size=page_size, total=total, total_pages=total_pages)


@router.get("/upload/{upload_id}/pnl/{fc_day_id}", response_model=FCDayDetail)
def get_pnl_detail(upload_id: str, fc_day_id: str, db: Session = Depends(get_db)) -> FCDayDetail:
    _get_upload_or_404(upload_id, db)
    r = db.query(FCDay).filter(FCDay.upload_id == upload_id, FCDay.id == fc_day_id).first()
    if r is None:
        raise NotFoundError(f"FC-day {fc_day_id} not found.")
    anomalies = db.query(AnomalyRow).filter(AnomalyRow.fc_day_id == fc_day_id).all()
    return _to_detail(r, anomalies)


@router.get("/upload/{upload_id}/anomalies", response_model=PaginatedResponse[AnomalyLogEntry])
def list_anomalies(
    upload_id: str,
    fc: str | None = None,
    severity: str | None = None,
    line_item: str | None = None,
    date_from: date_type | None = None,
    date_to: date_type | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
) -> PaginatedResponse:
    _get_upload_or_404(upload_id, db)
    q = db.query(AnomalyRow).filter(AnomalyRow.upload_id == upload_id)
    if fc:
        q = q.filter(AnomalyRow.fc_name == fc)
    if severity:
        q = q.filter(AnomalyRow.severity == severity.upper())
    if line_item:
        q = q.filter(AnomalyRow.line_item == line_item)
    if date_from:
        q = q.filter(AnomalyRow.date >= date_from)
    if date_to:
        q = q.filter(AnomalyRow.date <= date_to)

    total = q.count()
    rows = q.order_by(AnomalyRow.date, AnomalyRow.fc_name).offset((page - 1) * page_size).limit(page_size).all()

    items = [
        AnomalyLogEntry(
            date=a.date, fc_name=a.fc_name, line_item=a.line_item, actual_pct=a.actual_pct,
            target_range=f"{a.target_min}-{a.target_max}%", deviation=a.deviation,
            status=a.status, severity=a.severity,
        )
        for a in rows
    ]
    total_pages = max(1, (total + page_size - 1) // page_size)
    return PaginatedResponse(items=items, page=page, page_size=page_size, total=total, total_pages=total_pages)


@router.get("/upload/{upload_id}/digests")
def list_digests(
    upload_id: str,
    fc: str | None = None,
    date: date_type | None = None,
    color: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    _get_upload_or_404(upload_id, db)
    q = db.query(DigestRow).filter(DigestRow.upload_id == upload_id)
    if fc:
        q = q.filter(DigestRow.fc_name == fc)
    if date:
        q = q.filter(DigestRow.date == date)
    if color:
        q = q.filter(DigestRow.color_code == color.upper())
    rows = q.order_by(DigestRow.date, DigestRow.fc_name).all()
    return {"digests": [DigestResponse.model_validate(r) for r in rows]}


@router.get("/upload/{upload_id}/digests/{fc_name}/{digest_date}", response_model=DigestResponse)
def get_digest(upload_id: str, fc_name: str, digest_date: date_type, db: Session = Depends(get_db)) -> DigestRow:
    _get_upload_or_404(upload_id, db)
    row = (
        db.query(DigestRow)
        .filter(DigestRow.upload_id == upload_id, DigestRow.fc_name == fc_name, DigestRow.date == digest_date)
        .first()
    )
    if row is None:
        raise NotFoundError(f"Digest for {fc_name} on {digest_date} not found.")
    return row


@router.get("/upload/{upload_id}/export")
def export_excel(upload_id: str, db: Session = Depends(get_db)) -> FileResponse:
    _get_upload_or_404(upload_id, db)
    path = storage.report_path(upload_id)
    if not path.exists():
        raise NotFoundError("Report not yet generated for this upload.")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"pnl_report_{upload_id}.xlsx",
    )


@router.get("/upload/{upload_id}/export/anomalies")
def export_anomalies_csv(upload_id: str, db: Session = Depends(get_db)) -> StreamingResponse:
    _get_upload_or_404(upload_id, db)
    rows = (
        db.query(AnomalyRow)
        .filter(AnomalyRow.upload_id == upload_id)
        .order_by(AnomalyRow.date, AnomalyRow.fc_name)
        .all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "FC", "Line Item", "Actual %", "Target Min %", "Target Max %",
                      "Deviation", "Status", "Severity"])
    for a in rows:
        writer.writerow([a.date, a.fc_name, a.line_item, a.actual_pct, a.target_min,
                          a.target_max, a.deviation, a.status, a.severity])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=anomaly_log_{upload_id}.csv"},
    )
