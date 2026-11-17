from datetime import date

from app.config import Settings
from app.pipeline.compute_agent import ComputeAgent
from app.pipeline.detect_agent import DetectAgent
from app.types import AnomalyStatus, ColorCode, FCDayPnL, FCDayRecord, Severity


def settings() -> Settings:
    return Settings(_env_file=None)


def pnl_from_pct(revenue: float = 100_000, **pct) -> FCDayPnL:
    """Build a computed FCDayPnL from percentages (cost = pct% of revenue)."""
    defaults = dict(manpower=24.0, packaging=7.5, power_fuel=5.0, rent=11.5, equipment=3.5, overheads=5.0)
    defaults.update(pct)
    record = FCDayRecord(
        fc_name="FC-Test", date=date(2026, 11, 1), revenue=revenue,
        manpower_cost=revenue * defaults["manpower"] / 100,
        packaging_cost=revenue * defaults["packaging"] / 100,
        power_fuel=revenue * defaults["power_fuel"] / 100,
        fc_rent=revenue * defaults["rent"] / 100,
        equipment_rentals=revenue * defaults["equipment"] / 100,
        overheads=revenue * defaults["overheads"] / 100,
    )
    return ComputeAgent().compute_one(record)


def test_clean_day_green_no_anomalies():
    pnl = pnl_from_pct(manpower=27.6, packaging=9.7, power_fuel=6.8, rent=14.5, equipment=4.7, overheads=6.8)
    result = DetectAgent(settings()).detect_one(pnl)
    assert result.color_code == ColorCode.GREEN
    assert result.anomalies == []


def test_cm2_breach_red_high_severity():
    pnl = pnl_from_pct(manpower=36.0, packaging=9.5, power_fuel=11.0, rent=23.0, equipment=5.0, overheads=7.0)
    result = DetectAgent(settings()).detect_one(pnl)
    assert result.color_code == ColorCode.RED
    cm2_anomalies = [a for a in result.anomalies if a.line_item == "CM2"]
    assert len(cm2_anomalies) == 1
    assert cm2_anomalies[0].severity == Severity.HIGH
    assert cm2_anomalies[0].status == AnomalyStatus.BREACH_LOW


def test_line_item_only_breach_stays_green():
    # Packaging breach only; CM2 stays Green (Phase 0 LINEITEM_packaging_only)
    pnl = pnl_from_pct(manpower=25.0, packaging=12.0, power_fuel=6.8, rent=14.8, equipment=4.7, overheads=6.8)
    result = DetectAgent(settings()).detect_one(pnl)
    assert result.color_code == ColorCode.GREEN
    assert len(result.anomalies) == 1
    assert result.anomalies[0].line_item == "Packaging Cost"
    assert result.anomalies[0].severity == Severity.MEDIUM
    assert result.anomalies[0].status == AnomalyStatus.BREACH_HIGH


def test_suspicious_high_cm2_blue_high_severity_no_line_breach():
    # Midpoint costs -> Blue with zero line-item anomalies (Phase 0 finding)
    pnl = pnl_from_pct(manpower=24.0, packaging=7.5, power_fuel=5.0, rent=11.5, equipment=3.5, overheads=5.0)
    result = DetectAgent(settings()).detect_one(pnl)
    assert result.color_code == ColorCode.BLUE
    assert len(result.anomalies) == 1
    assert result.anomalies[0].line_item == "CM2"
    assert result.anomalies[0].severity == Severity.HIGH
    assert result.anomalies[0].status == AnomalyStatus.BREACH_HIGH


def test_yellow_zone_lower():
    pnl = pnl_from_pct(manpower=34.0, packaging=9.8, power_fuel=9.5, rent=21.0, equipment=4.8, overheads=7.0)
    result = DetectAgent(settings()).detect_one(pnl)
    assert result.color_code == ColorCode.YELLOW
    assert 12 <= result.cm2_pct < 15


def test_yellow_zone_upper():
    pnl = pnl_from_pct(manpower=27.0, packaging=9.2, power_fuel=6.5, rent=13.8, equipment=4.3, overheads=6.3)
    result = DetectAgent(settings()).detect_one(pnl)
    assert result.color_code == ColorCode.YELLOW
    assert 30 < result.cm2_pct <= 33


def test_zero_revenue_red_and_zero_revenue_anomaly():
    record = FCDayRecord(
        fc_name="FC-Test", date=date(2026, 11, 1), revenue=0,
        manpower_cost=5000, packaging_cost=0, power_fuel=2000,
        fc_rent=18000, equipment_rentals=3000, overheads=4000,
    )
    pnl = ComputeAgent().compute_one(record)
    result = DetectAgent(settings()).detect_one(pnl)
    assert result.color_code == ColorCode.RED
    assert len(result.anomalies) == 1
    assert result.anomalies[0].status == AnomalyStatus.ZERO_REVENUE
    assert result.anomalies[0].severity == Severity.INFO


def test_multiple_anomalies_sorted_by_severity():
    # Red day with several line-item breaches (HIGH CM anomalies + MEDIUM line anomalies)
    pnl = pnl_from_pct(manpower=36.0, packaging=9.5, power_fuel=11.0, rent=23.0, equipment=5.0, overheads=7.0)
    result = DetectAgent(settings()).detect_one(pnl)
    assert len(result.anomalies) >= 4  # CM1, CM2, Manpower, Power&Fuel, Rent
    severities = [a.severity for a in result.anomalies]
    ranks = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.INFO: 2}
    assert severities == sorted(severities, key=lambda s: ranks[s])
    high_items = {a.line_item for a in result.anomalies if a.severity == Severity.HIGH}
    assert "CM1" in high_items
    assert "CM2" in high_items


def test_custom_thresholds_adapt_detection():
    pnl = pnl_from_pct(manpower=30.0)  # 30% breaches default max 28, but not a custom max of 35
    default_result = DetectAgent(settings()).detect_one(pnl)
    assert any(a.line_item == "Manpower Cost" for a in default_result.anomalies)

    custom = Settings(_env_file=None, target_manpower_max=35)
    custom_result = DetectAgent(custom).detect_one(pnl)
    assert not any(a.line_item == "Manpower Cost" for a in custom_result.anomalies)


def test_line_item_breach_deviation_and_target_use_base_range_not_tolerance():
    pnl = pnl_from_pct(manpower=36.0, packaging=9.5, power_fuel=11.0, rent=23.0, equipment=5.0, overheads=7.0)
    result = DetectAgent(settings()).detect_one(pnl)
    cm2 = next(a for a in result.anomalies if a.line_item == "CM2")
    assert cm2.target_min == 15
    assert cm2.target_max == 30
    assert cm2.deviation == round(result.cm2_pct - 15, 1)
