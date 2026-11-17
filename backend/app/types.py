"""Core pipeline data types shared by all agents."""

from datetime import date as date_type
from enum import StrEnum

from pydantic import BaseModel


class ColorCode(StrEnum):
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"
    BLUE = "BLUE"


class AnomalyStatus(StrEnum):
    BREACH_LOW = "BREACH_LOW"
    BREACH_HIGH = "BREACH_HIGH"
    ZERO_REVENUE = "ZERO_REVENUE"


class Severity(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    INFO = "INFO"


class FCDayRecord(BaseModel):
    """Raw parsed row from the input file (Ingest Agent output)."""

    fc_name: str
    date: date_type
    revenue: float
    manpower_cost: float
    packaging_cost: float
    power_fuel: float
    fc_rent: float
    equipment_rentals: float
    overheads: float


class Anomaly(BaseModel):
    line_item: str
    actual_pct: float
    target_min: float
    target_max: float
    deviation: float
    status: AnomalyStatus
    severity: Severity


class FCDayPnL(BaseModel):
    """Fully computed P&L for one FC-day (Compute + Detect Agent output)."""

    fc_name: str
    date: date_type
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
    # Detection results (empty/default until Detect Agent runs)
    color_code: ColorCode | None = None
    anomalies: list[Anomaly] = []
    insight: str = ""


class FCDayDigest(BaseModel):
    """Insight text + metadata for one FC-day (Insight Agent output)."""

    fc_name: str
    date: date_type
    color_code: ColorCode
    anomalies: list[Anomaly]
    insight_text: str
    generation_mode: str  # "llm" or "rule"
