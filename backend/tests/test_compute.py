from datetime import date

from app.pipeline.compute_agent import ComputeAgent
from app.types import FCDayRecord


def make_record(**overrides) -> FCDayRecord:
    base = dict(
        fc_name="FC-Delhi", date=date(2026, 11, 1), revenue=213400,
        manpower_cost=59199, packaging_cost=20471, power_fuel=14308,
        fc_rent=31279, equipment_rentals=10123, overheads=14102,
    )
    base.update(overrides)
    return FCDayRecord(**base)


def test_matches_hand_calculated_clean_day():
    # FC-Delhi 2026-11-01 from Phase 0 spike_findings.md
    pnl = ComputeAgent().compute_one(make_record())
    assert pnl.cm1 == 133730
    assert pnl.cm1_pct == 62.7  # rounded to 1 decimal (62.67 -> 62.7)
    assert pnl.cm2 == 63918
    assert pnl.cm2_pct == 30.0  # 63918/213400*100 = 29.95 -> rounds to 30.0
    assert pnl.manpower_pct == 27.7
    assert pnl.packaging_pct == 9.6


def test_matches_hand_calculated_red_day():
    # FC-Delhi 2026-11-05 from Phase 0 spike_findings.md
    record = make_record(
        date=date(2026, 11, 5), revenue=237400, manpower_cost=85464,
        packaging_cost=22553, power_fuel=26114, fc_rent=54602,
        equipment_rentals=11870, overheads=16618,
    )
    pnl = ComputeAgent().compute_one(record)
    assert pnl.cm1 == 129383
    assert pnl.cm1_pct == 54.5
    assert pnl.cm2 == 20179
    assert pnl.cm2_pct == 8.5


def test_matches_hand_calculated_blue_day():
    # FC-Bangalore 2026-11-06 from Phase 0 spike_findings.md
    record = make_record(
        fc_name="FC-Bangalore", date=date(2026, 11, 6), revenue=154100,
        manpower_cost=36984, packaging_cost=11558, power_fuel=7705,
        fc_rent=17722, equipment_rentals=5394, overheads=7705,
    )
    pnl = ComputeAgent().compute_one(record)
    assert pnl.cm1 == 105558
    assert pnl.cm1_pct == 68.5
    assert pnl.cm2 == 67032
    assert pnl.cm2_pct == 43.5


def test_zero_revenue_all_percentages_zero_no_crash():
    record = make_record(
        revenue=0, manpower_cost=5000, packaging_cost=0, power_fuel=2000,
        fc_rent=18000, equipment_rentals=3000, overheads=4000,
    )
    pnl = ComputeAgent().compute_one(record)
    assert pnl.cm1_pct == 0.0
    assert pnl.cm2_pct == 0.0
    assert pnl.manpower_pct == 0.0
    assert pnl.packaging_pct == 0.0
    assert pnl.power_fuel_pct == 0.0
    assert pnl.fc_rent_pct == 0.0
    assert pnl.equipment_pct == 0.0
    assert pnl.overheads_pct == 0.0
    # absolute cm1/cm2 still computed normally (no division involved)
    assert pnl.cm1 == 0 - 5000 - 0
    assert pnl.cm2 == pnl.cm1 - 2000 - 18000 - 3000 - 4000


def test_negative_costs_computed_correctly():
    record = make_record(revenue=100000, packaging_cost=-500)
    pnl = ComputeAgent().compute_one(record)
    assert pnl.cm1 == 100000 - 59199 - (-500)
    assert pnl.packaging_pct == round(-500 / 100000 * 100, 1)


def test_single_and_batch_processing_consistent():
    records = [make_record(), make_record(date=date(2026, 11, 2))]
    agent = ComputeAgent()
    batch_result = agent.run(records)
    single_results = [agent.compute_one(r) for r in records]
    assert batch_result == single_results


def test_sanity_cm1_minus_remaining_costs_equals_cm2_and_cm2_plus_costs_equals_revenue():
    pnl = ComputeAgent().compute_one(make_record())
    remaining = pnl.power_fuel + pnl.fc_rent + pnl.equipment_rentals + pnl.overheads
    assert pnl.cm1 - remaining == pnl.cm2
    total_costs = (
        pnl.manpower_cost + pnl.packaging_cost + pnl.power_fuel
        + pnl.fc_rent + pnl.equipment_rentals + pnl.overheads
    )
    assert pnl.revenue - total_costs == pnl.cm2
