"""Detect Agent — compare each FC-day's P&L against configured target ranges,
flag anomalies, and assign the daily color code.

Anomaly.target_min/target_max always hold the *base* target range (not the
tolerance-widened band used to decide whether CM1/CM2 gets flagged) so the
Insight Agent and UI can always show "target: 15-30%" rather than the
internal ±3pp flagging threshold.
"""

from app.config import Settings, TargetRange
from app.types import Anomaly, AnomalyStatus, ColorCode, FCDayPnL, Severity

_SEVERITY_RANK = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.INFO: 2}

LINE_ITEMS: list[tuple[str, str]] = [
    ("Manpower Cost", "manpower_pct"),
    ("Packaging Cost", "packaging_pct"),
    ("Power & Fuel", "power_fuel_pct"),
    ("FC Rent", "fc_rent_pct"),
    ("Equipment Rentals", "equipment_pct"),
    ("Overheads", "overheads_pct"),
]


def _color_for(cm2_pct: float) -> ColorCode:
    if cm2_pct < 12:
        return ColorCode.RED
    if cm2_pct < 15:
        return ColorCode.YELLOW
    if cm2_pct <= 30:
        return ColorCode.GREEN
    if cm2_pct <= 33:
        return ColorCode.YELLOW
    return ColorCode.BLUE


def _check_line_item(actual_pct: float, label: str, target: TargetRange) -> Anomaly | None:
    if actual_pct < target.min_pct:
        return Anomaly(
            line_item=label, actual_pct=actual_pct,
            target_min=target.min_pct, target_max=target.max_pct,
            deviation=round(actual_pct - target.min_pct, 1),
            status=AnomalyStatus.BREACH_LOW, severity=Severity.MEDIUM,
        )
    if actual_pct > target.max_pct:
        return Anomaly(
            line_item=label, actual_pct=actual_pct,
            target_min=target.min_pct, target_max=target.max_pct,
            deviation=round(actual_pct - target.max_pct, 1),
            status=AnomalyStatus.BREACH_HIGH, severity=Severity.MEDIUM,
        )
    return None


def _check_margin(actual_pct: float, label: str, target: TargetRange, tolerance: float) -> Anomaly | None:
    effective_min = target.min_pct - tolerance
    effective_max = target.max_pct + tolerance
    if actual_pct < effective_min:
        return Anomaly(
            line_item=label, actual_pct=actual_pct,
            target_min=target.min_pct, target_max=target.max_pct,
            deviation=round(actual_pct - target.min_pct, 1),
            status=AnomalyStatus.BREACH_LOW, severity=Severity.HIGH,
        )
    if actual_pct > effective_max:
        return Anomaly(
            line_item=label, actual_pct=actual_pct,
            target_min=target.min_pct, target_max=target.max_pct,
            deviation=round(actual_pct - target.max_pct, 1),
            status=AnomalyStatus.BREACH_HIGH, severity=Severity.HIGH,
        )
    return None


class DetectAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, pnl_data: list[FCDayPnL]) -> list[FCDayPnL]:
        return [self.detect_one(p) for p in pnl_data]

    def detect_one(self, pnl: FCDayPnL) -> FCDayPnL:
        if pnl.revenue == 0:
            anomaly = Anomaly(
                line_item="Revenue", actual_pct=0.0, target_min=0.0, target_max=0.0,
                deviation=0.0, status=AnomalyStatus.ZERO_REVENUE, severity=Severity.INFO,
            )
            return pnl.model_copy(update={"anomalies": [anomaly], "color_code": ColorCode.RED})

        anomalies: list[Anomaly] = []
        ranges = self.settings.line_item_ranges()
        for label, attr in LINE_ITEMS:
            anomaly = _check_line_item(getattr(pnl, attr), label, ranges[label])
            if anomaly:
                anomalies.append(anomaly)

        cm1_anomaly = _check_margin(pnl.cm1_pct, "CM1", self.settings.cm1_range, self.settings.cm_tolerance)
        if cm1_anomaly:
            anomalies.append(cm1_anomaly)
        cm2_anomaly = _check_margin(pnl.cm2_pct, "CM2", self.settings.cm2_range, self.settings.cm_tolerance)
        if cm2_anomaly:
            anomalies.append(cm2_anomaly)

        anomalies.sort(key=lambda a: _SEVERITY_RANK[a.severity])
        color = _color_for(pnl.cm2_pct)

        return pnl.model_copy(update={"anomalies": anomalies, "color_code": color})
