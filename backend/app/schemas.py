"""Pydantic request/response models matching docs/api.md."""

from datetime import date as date_type
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
    total_pages: int


class UploadCreateResponse(BaseModel):
    upload_id: str
    status: str
    filename: str


class UploadSummary(BaseModel):
    id: str
    filename: str
    name: str | None = None
    status: str
    error_message: str | None = None
    fc_count: int
    day_count: int
    anomaly_count: int
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class AnomalyInline(BaseModel):
    line_item: str
    actual_pct: float
    target_min: float
    target_max: float
    deviation: float
    status: str
    severity: str

    model_config = {"from_attributes": True}


class FCDaySummary(BaseModel):
    """Lightweight version for the dashboard grid."""

    fc_name: str
    date: date_type
    cm2_pct: float
    color_code: str
    anomaly_count: int


class FCDayDetail(BaseModel):
    id: str
    fc_name: str
    date: date_type
    revenue: float
    manpower_cost: float
    packaging_cost: float
    power_fuel: float
    fc_rent: float
    equipment_rentals: float
    overheads: float
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
    color_code: str
    anomalies: list[AnomalyInline]
    insight: str

    model_config = {"from_attributes": True}


class DashboardData(BaseModel):
    """Cross-FC daily status grid."""

    dates: list[date_type]
    fcs: list[str]
    grid: dict[str, list[FCDaySummary]]  # fc_name -> one entry per date


class AnomalyLogEntry(BaseModel):
    date: date_type
    fc_name: str
    line_item: str
    actual_pct: float
    target_range: str  # e.g. "20-28%"
    deviation: float
    status: str
    severity: str


class DigestResponse(BaseModel):
    fc_name: str
    date: date_type
    color_code: str
    summary_text: str
    html_content: str
    generation_mode: str

    model_config = {"from_attributes": True}


class ConfigRangePair(BaseModel):
    min: float
    max: float


class ConfigResponse(BaseModel):
    targets: dict[str, ConfigRangePair]
    cm1: ConfigRangePair
    cm2: ConfigRangePair
    cm_tolerance: float
    max_file_mb: int
    notify_channel: str


class HealthResponse(BaseModel):
    status: str
    version: str
