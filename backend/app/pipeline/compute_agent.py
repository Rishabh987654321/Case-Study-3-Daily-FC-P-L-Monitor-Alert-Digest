"""Compute Agent — pure math: CM1, CM2, and every cost line as % of revenue.

No side effects, no database access. Zero revenue never raises — all
percentage fields are simply set to 0 for that day (the absolute cm1/cm2
money amounts are still real, since no division is involved there).
"""

from app.types import FCDayPnL, FCDayRecord


def _pct(amount: float, revenue: float) -> float:
    if revenue == 0:
        return 0.0
    return round(amount / revenue * 100, 1)


class ComputeAgent:
    def run(self, records: list[FCDayRecord]) -> list[FCDayPnL]:
        return [self.compute_one(r) for r in records]

    def compute_one(self, r: FCDayRecord) -> FCDayPnL:
        cm1 = r.revenue - r.manpower_cost - r.packaging_cost
        cm2 = cm1 - r.power_fuel - r.fc_rent - r.equipment_rentals - r.overheads

        return FCDayPnL(
            fc_name=r.fc_name,
            date=r.date,
            revenue=r.revenue,
            manpower_cost=r.manpower_cost,
            packaging_cost=r.packaging_cost,
            power_fuel=r.power_fuel,
            fc_rent=r.fc_rent,
            equipment_rentals=r.equipment_rentals,
            overheads=r.overheads,
            cm1=cm1,
            cm1_pct=_pct(cm1, r.revenue),
            cm2=cm2,
            cm2_pct=_pct(cm2, r.revenue),
            manpower_pct=_pct(r.manpower_cost, r.revenue),
            packaging_pct=_pct(r.packaging_cost, r.revenue),
            power_fuel_pct=_pct(r.power_fuel, r.revenue),
            fc_rent_pct=_pct(r.fc_rent, r.revenue),
            equipment_pct=_pct(r.equipment_rentals, r.revenue),
            overheads_pct=_pct(r.overheads, r.revenue),
        )
