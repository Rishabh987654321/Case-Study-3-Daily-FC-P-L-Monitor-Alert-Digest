"""Insight Agent — plain-language insight per FC-day.

Primary mode: local LLM via Ollama (free, no API key, data stays local).
Fallback mode: deterministic rule-based templates, used whenever Ollama is
unavailable, times out, or its response fails validation. INSIGHT_MODE=rule
skips the LLM entirely (used by default in tests so they never depend on a
running Ollama instance); INSIGHT_MODE=llm is strict and raises if Ollama
fails instead of silently falling back.

In "auto" mode, the whole batch is also bounded by a wall-clock time budget
(settings.insight_batch_budget_seconds): once that much time has been spent
attempting LLM calls, every remaining FC-day in this run falls back to
rule-based instantly, so a large upload's insight step can't scale up to
minutes just because the file has hundreds of rows.
"""

import re
import time

import httpx

from app.config import Settings
from app.types import Anomaly, AnomalyStatus, ColorCode, FCDayDigest, FCDayPnL

_COLOR_MEANINGS = {
    ColorCode.RED: "Margin crisis — below 12%",
    ColorCode.YELLOW: "Warning zone — approaching limits",
    ColorCode.GREEN: "Healthy — within target",
    ColorCode.BLUE: "Suspicious — above 33%, check for underreported costs",
}

_LINE_ITEM_PCT_FIELDS = [
    ("Manpower Cost", "manpower_pct"),
    ("Packaging Cost", "packaging_pct"),
    ("Power & Fuel", "power_fuel_pct"),
    ("FC Rent", "fc_rent_pct"),
    ("Equipment Rentals", "equipment_pct"),
    ("Overheads", "overheads_pct"),
]


def _midpoint(a: Anomaly) -> float:
    return (a.target_min + a.target_max) / 2


def _impact(a: Anomaly, revenue: float) -> float:
    return abs(a.actual_pct - _midpoint(a)) * revenue


def _format_breach(a: Anomaly) -> str:
    if a.status == AnomalyStatus.BREACH_HIGH:
        return f"{a.line_item} at {a.actual_pct}% (target max {a.target_max}%)"
    return f"{a.line_item} at {a.actual_pct}% (target min {a.target_min}%)"


def _variant(day: FCDayPnL) -> int:
    """Deterministic 0/1 selector so phrasing varies across days without randomness."""
    return hash((day.fc_name, day.date)) % 2


class InsightAgent:
    # Below this many seconds of remaining budget, don't even attempt an LLM
    # call — a request that's doomed to be cut off almost immediately just
    # wastes a round trip; go straight to the rule-based template instead.
    _MIN_USEFUL_TIMEOUT = 1.0

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.ollama_url = settings.ollama_base_url
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout
        self.mode = settings.insight_mode
        self.batch_budget = settings.insight_batch_budget_seconds

    async def run(self, pnl_data: list[FCDayPnL]) -> list[FCDayDigest]:
        digests = []
        batch_start = time.monotonic()
        for day in pnl_data:
            timeout_override = None
            budget_exhausted = False
            if self.mode == "auto":
                remaining = self.batch_budget - (time.monotonic() - batch_start)
                if remaining < self._MIN_USEFUL_TIMEOUT:
                    budget_exhausted = True
                else:
                    timeout_override = min(self.timeout, remaining)

            if budget_exhausted:
                insight, mode = self._rule_insight(day), "rule"
            else:
                insight, mode = await self._generate_insight(day, timeout_override)

            digests.append(FCDayDigest(
                fc_name=day.fc_name,
                date=day.date,
                color_code=day.color_code,
                anomalies=day.anomalies,
                insight_text=insight,
                generation_mode=mode,
            ))
        return digests

    async def _generate_insight(self, day: FCDayPnL, timeout_override: float | None = None) -> tuple[str, str]:
        if self.mode in ("auto", "llm"):
            try:
                result = await self._llm_insight(day, timeout_override)
                if result:
                    return result, "llm"
            except Exception:
                if self.mode == "llm":
                    raise
        return self._rule_insight(day), "rule"

    async def _llm_insight(self, day: FCDayPnL, timeout_override: float | None = None) -> str | None:
        prompt = self._build_prompt(day)
        timeout = self.timeout if timeout_override is None else timeout_override
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 200},
                },
            )
            resp.raise_for_status()
            text = resp.json()["response"].strip()

        if not self._validate_llm_response(text, day):
            return None
        return text

    def _build_prompt(self, day: FCDayPnL) -> str:
        anomaly_lines = "\n".join(
            f"- {a.line_item}: {a.actual_pct}% (target: {a.target_min}-{a.target_max}%, "
            f"deviation: {a.deviation:+.1f}pp, severity: {a.severity})"
            for a in day.anomalies
        ) or "None"

        return f"""You are an FC financial analyst. Analyze this daily P&L data and write a concise insight paragraph.

FC: {day.fc_name}
Date: {day.date}
Revenue: ₹{day.revenue:,.0f}
CM1: {day.cm1_pct}% (target: 65-70%)
CM2: {day.cm2_pct}% (target: 15-30%)
Color Code: {day.color_code} ({_COLOR_MEANINGS.get(day.color_code, '')})

Cost Breakdown (% of Revenue):
- Manpower: {day.manpower_pct}% (target: 20-28%)
- Packaging: {day.packaging_pct}% (target: 5-10%)
- Power & Fuel: {day.power_fuel_pct}% (target: 3-7%)
- FC Rent: {day.fc_rent_pct}% (target: 8-15%)
- Equipment Rentals: {day.equipment_pct}% (target: 2-5%)
- Overheads: {day.overheads_pct}% (target: 3-7%)

Anomalies detected:
{anomaly_lines}

Write 2-3 sentences: state the key finding, identify the top cost driver(s), and recommend one specific action. Use actual numbers from the data above. Be direct and specific."""

    def _validate_llm_response(self, text: str, day: FCDayPnL) -> bool:
        if not text or len(text) < 20 or len(text) > 1000:
            return False
        normalized = text.replace("!", ".").replace("?", ".")
        # Split on sentence-ending periods only — a naive split also breaks on
        # decimal points ("10.5%"), which financial insight text is full of.
        sentences = [s.strip() for s in re.split(r"(?<!\d)\.(?!\d)", normalized) if s.strip()]
        if len(sentences) < 1 or len(sentences) > 6:
            return False
        key_numbers = [f"{day.cm2_pct}", f"{day.cm1_pct}"]
        if not any(n in text for n in key_numbers):
            return False
        return True

    # ------------------------------------------------------------------
    # Rule-based fallback (deterministic, no network calls)
    # ------------------------------------------------------------------

    def _rule_insight(self, day: FCDayPnL) -> str:
        zero_rev = next((a for a in day.anomalies if a.status == AnomalyStatus.ZERO_REVENUE), None)
        if zero_rev:
            return self._zero_revenue_text(day)

        cm1_anomaly = next((a for a in day.anomalies if a.line_item == "CM1"), None)
        line_anomalies = [
            a for a in day.anomalies
            if a.line_item not in ("CM1", "CM2") and a.status != AnomalyStatus.ZERO_REVENUE
        ]
        ranked = sorted(line_anomalies, key=lambda a: -_impact(a, day.revenue))

        if day.color_code == ColorCode.RED:
            text = self._red_text(day, ranked)
        elif day.color_code == ColorCode.BLUE:
            text = self._blue_text(day)
        elif day.color_code == ColorCode.YELLOW:
            text = self._yellow_text(day, ranked)
        elif ranked or cm1_anomaly:
            text = self._line_item_only_text(day, ranked)
        else:
            text = self._clean_text(day)

        if cm1_anomaly and day.color_code != ColorCode.RED:
            text += (
                f" CM1 is also outside target at {day.cm1_pct}% (target 65-70%) — "
                "review direct costs (manpower + packaging)."
            )
        return text

    def _clean_text(self, day: FCDayPnL) -> str:
        if _variant(day) == 0:
            return f"All metrics within target ranges for {day.fc_name} on {day.date}. CM2 = {day.cm2_pct}% (Green)."
        return (
            f"{day.fc_name} had a clean day on {day.date} — every metric sat within target, "
            f"with CM2 at {day.cm2_pct}% (Green)."
        )

    def _red_text(self, day: FCDayPnL, ranked: list[Anomaly]) -> str:
        top_breaches = "; ".join(_format_breach(a) for a in ranked[:3]) or "no individual line items flagged"
        if _variant(day) == 0:
            return (
                f"On {day.date}, {day.fc_name} CM2 = {day.cm2_pct}% (below 12%). "
                f"{top_breaches}. Recommend immediate cost audit."
            )
        return (
            f"{day.fc_name}'s margin fell to {day.cm2_pct}% on {day.date}, well under the 12% floor, "
            f"driven mainly by {top_breaches}. Recommend an immediate cost audit and escalate to the FC head."
        )

    def _blue_text(self, day: FCDayPnL) -> str:
        lowest = sorted(
            _LINE_ITEM_PCT_FIELDS,
            key=lambda pair: getattr(day, pair[1]) - _line_item_min(self.settings, pair[0]),
        )[:3]
        lowest_desc = "; ".join(
            f"{name} at {getattr(day, attr)}% (target min {_line_item_min(self.settings, name)}%)"
            for name, attr in lowest
        )
        if _variant(day) == 0:
            return (
                f"On {day.date}, {day.fc_name} CM2 = {day.cm2_pct}% (above 33% — suspiciously high). "
                f"Verify that all costs are reported, especially: {lowest_desc}. "
                "Recommend reconciliation with actuals."
            )
        return (
            f"{day.fc_name}'s CM2 reached an unusually high {day.cm2_pct}% on {day.date} "
            f"(above the 33% ceiling) — a sign that costs may be underreported, particularly {lowest_desc}. "
            "Recommend reconciling with actuals before treating this as good news."
        )

    def _yellow_text(self, day: FCDayPnL, ranked: list[Anomaly]) -> str:
        direction = "upper" if day.cm2_pct > 30 else "lower"
        watch = "; ".join(_format_breach(a) for a in ranked[:3]) or "no individual line items flagged yet"
        if _variant(day) == 0:
            return (
                f"On {day.date}, {day.fc_name} CM2 = {day.cm2_pct}% (approaching {direction} limit — warning zone). "
                f"Watch: {watch}."
            )
        return (
            f"{day.fc_name} is drifting toward the {direction} edge of its CM2 band on {day.date} "
            f"at {day.cm2_pct}% — a warning sign worth tracking. Keep an eye on {watch}."
        )

    def _line_item_only_text(self, day: FCDayPnL, ranked: list[Anomaly]) -> str:
        n = len(ranked)
        items = "; ".join(_format_breach(a) for a in ranked) or "CM1"
        plural = "s" if n != 1 else ""
        if n == 1:
            a = ranked[0]
            direction = "above target max" if a.status == AnomalyStatus.BREACH_HIGH else "below target min"
            action = f"Review {a.line_item} spend — {abs(a.deviation)}pp {direction}."
        elif n > 1:
            action = f"Cost audit needed — {n} items outside target."
        else:
            action = "Review direct costs (manpower + packaging)."

        if _variant(day) == 0:
            return (
                f"On {day.date}, {day.fc_name} margins are healthy (CM2 = {day.cm2_pct}%) but "
                f"{n} line item{plural} breached target{plural}: {items}. {action} "
                "No immediate action needed beyond that — monitor over the next few days."
            )
        return (
            f"{day.fc_name}'s overall margin on {day.date} is healthy at {day.cm2_pct}% CM2, though "
            f"{n} line item{plural} drifted outside target — {items}. {action} Worth monitoring, no urgent action needed."
        )

    def _zero_revenue_text(self, day: FCDayPnL) -> str:
        if _variant(day) == 0:
            return (
                f"No revenue was recorded for {day.fc_name} on {day.date}. "
                "Verify data: zero revenue recorded. Check if FC was operational."
            )
        return (
            f"{day.fc_name} shows ₹0 revenue on {day.date} — this needs verification. "
            "Check if the FC was operational before treating this as a real zero-revenue day."
        )


def _line_item_min(settings: Settings, label: str) -> float:
    return settings.line_item_ranges()[label].min_pct
