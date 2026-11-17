import asyncio
import time
from datetime import date
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.config import Settings
from app.pipeline.compute_agent import ComputeAgent
from app.pipeline.detect_agent import DetectAgent
from app.pipeline.insight_agent import InsightAgent
from app.types import FCDayPnL, FCDayRecord


def build_day(settings: Settings, **pct) -> FCDayPnL:
    revenue = pct.pop("revenue", 100_000)
    defaults = dict(manpower=24.0, packaging=7.5, power_fuel=5.0, rent=11.5, equipment=3.5, overheads=5.0)
    defaults.update(pct)
    record = FCDayRecord(
        fc_name=pct.get("fc_name", "FC-Test"), date=date(2026, 11, 1), revenue=revenue,
        manpower_cost=revenue * defaults["manpower"] / 100,
        packaging_cost=revenue * defaults["packaging"] / 100,
        power_fuel=revenue * defaults["power_fuel"] / 100,
        fc_rent=revenue * defaults["rent"] / 100,
        equipment_rentals=revenue * defaults["equipment"] / 100,
        overheads=revenue * defaults["overheads"] / 100,
    )
    pnl = ComputeAgent().compute_one(record)
    return DetectAgent(settings).detect_one(pnl)


@pytest.fixture
def rule_settings() -> Settings:
    return Settings(_env_file=None, insight_mode="rule")


@pytest.mark.asyncio
async def test_green_day_insight_mentions_within_target(rule_settings):
    day = build_day(rule_settings, manpower=27.6, packaging=9.7, power_fuel=6.8, rent=14.5, equipment=4.7, overheads=6.8)
    digests = await InsightAgent(rule_settings).run([day])
    assert len(digests) == 1
    assert digests[0].generation_mode == "rule"
    assert "within target" in digests[0].insight_text.lower()
    assert str(day.cm2_pct) in digests[0].insight_text


@pytest.mark.asyncio
async def test_red_day_insight_mentions_breaches_and_audit(rule_settings):
    day = build_day(rule_settings, manpower=36.0, packaging=9.5, power_fuel=11.0, rent=23.0, equipment=5.0, overheads=7.0)
    digests = await InsightAgent(rule_settings).run([day])
    text = digests[0].insight_text.lower()
    assert "audit" in text or "review" in text
    assert "manpower" in text
    assert str(day.cm2_pct) in digests[0].insight_text


@pytest.mark.asyncio
async def test_blue_day_insight_mentions_suspicious_underreported(rule_settings):
    day = build_day(rule_settings, manpower=24.0, packaging=7.5, power_fuel=5.0, rent=11.5, equipment=3.5, overheads=5.0)
    digests = await InsightAgent(rule_settings).run([day])
    text = digests[0].insight_text.lower()
    assert "suspicious" in text or "underreported" in text


@pytest.mark.asyncio
async def test_yellow_day_insight_mentions_approaching_or_warning(rule_settings):
    day = build_day(rule_settings, manpower=34.0, packaging=9.8, power_fuel=9.5, rent=21.0, equipment=4.8, overheads=7.0)
    digests = await InsightAgent(rule_settings).run([day])
    text = digests[0].insight_text.lower()
    assert "approaching" in text or "warning" in text


@pytest.mark.asyncio
async def test_line_item_only_breach_insight_mentions_items_and_monitor(rule_settings):
    day = build_day(rule_settings, manpower=25.0, packaging=12.0, power_fuel=6.8, rent=14.8, equipment=4.7, overheads=6.8)
    digests = await InsightAgent(rule_settings).run([day])
    text = digests[0].insight_text.lower()
    assert "packaging" in text
    assert "monitor" in text


@pytest.mark.asyncio
async def test_zero_revenue_insight(rule_settings):
    record = FCDayRecord(
        fc_name="FC-Test", date=date(2026, 11, 1), revenue=0,
        manpower_cost=5000, packaging_cost=0, power_fuel=2000,
        fc_rent=18000, equipment_rentals=3000, overheads=4000,
    )
    pnl = ComputeAgent().compute_one(record)
    day = DetectAgent(rule_settings).detect_one(pnl)
    digests = await InsightAgent(rule_settings).run([day])
    text = digests[0].insight_text.lower()
    assert "zero revenue" in text or "₹0" in digests[0].insight_text
    assert "operational" in text


@pytest.mark.asyncio
async def test_multiple_anomalies_ranked_by_impact_in_text(rule_settings):
    # Manpower is the biggest deviation from its midpoint; should appear before weaker breaches.
    day = build_day(rule_settings, manpower=40.0, packaging=9.5, power_fuel=14.0, rent=13.0, equipment=10.0, overheads=6.5)
    digests = await InsightAgent(rule_settings).run([day])
    text = digests[0].insight_text
    manpower_idx = text.find("Manpower")
    power_idx = text.find("Power & Fuel")
    equipment_idx = text.find("Equipment")
    assert manpower_idx != -1 and power_idx != -1 and equipment_idx != -1
    # Manpower has the largest impact (deviation x revenue) and should be ranked first
    assert manpower_idx < power_idx < equipment_idx


@pytest.mark.asyncio
async def test_generation_mode_is_rule_when_mode_is_rule(rule_settings):
    day = build_day(rule_settings)
    digests = await InsightAgent(rule_settings).run([day])
    assert digests[0].generation_mode == "rule"


@pytest.mark.asyncio
async def test_llm_valid_response_is_accepted():
    settings = Settings(_env_file=None, insight_mode="llm")
    day = build_day(settings, manpower=36.0, packaging=9.5, power_fuel=11.0, rent=23.0, equipment=5.0, overheads=7.0)
    fake_text = f"CM2 dropped to {day.cm2_pct}% today, mainly due to high manpower spend. Recommend a cost review."

    mock_response = httpx.Response(200, json={"response": fake_text}, request=httpx.Request("POST", "http://test"))
    with patch.object(httpx.AsyncClient, "post", new=AsyncMock(return_value=mock_response)):
        digests = await InsightAgent(settings).run([day])
    assert digests[0].generation_mode == "llm"
    assert digests[0].insight_text == fake_text


@pytest.mark.asyncio
async def test_llm_response_too_long_falls_back_to_rule():
    settings = Settings(_env_file=None, insight_mode="auto")
    day = build_day(settings, manpower=36.0, packaging=9.5, power_fuel=11.0, rent=23.0, equipment=5.0, overheads=7.0)
    too_long = (f"CM2 is {day.cm2_pct}%. " + "This is filler text to pad the length out. " * 30)

    mock_response = httpx.Response(200, json={"response": too_long}, request=httpx.Request("POST", "http://test"))
    with patch.object(httpx.AsyncClient, "post", new=AsyncMock(return_value=mock_response)):
        digests = await InsightAgent(settings).run([day])
    assert digests[0].generation_mode == "rule"


@pytest.mark.asyncio
async def test_llm_response_without_numbers_falls_back_to_rule():
    settings = Settings(_env_file=None, insight_mode="auto")
    day = build_day(settings, manpower=36.0, packaging=9.5, power_fuel=11.0, rent=23.0, equipment=5.0, overheads=7.0)
    no_numbers = "The centre is performing poorly and needs a cost review immediately."

    mock_response = httpx.Response(200, json={"response": no_numbers}, request=httpx.Request("POST", "http://test"))
    with patch.object(httpx.AsyncClient, "post", new=AsyncMock(return_value=mock_response)):
        digests = await InsightAgent(settings).run([day])
    assert digests[0].generation_mode == "rule"


@pytest.mark.asyncio
async def test_ollama_unavailable_auto_mode_falls_back_gracefully():
    settings = Settings(_env_file=None, insight_mode="auto")
    day = build_day(settings)

    with patch.object(httpx.AsyncClient, "post", new=AsyncMock(side_effect=httpx.ConnectError("refused"))):
        digests = await InsightAgent(settings).run([day])
    assert digests[0].generation_mode == "rule"
    assert digests[0].insight_text  # still produced a usable insight


@pytest.mark.asyncio
async def test_ollama_unavailable_strict_llm_mode_raises():
    settings = Settings(_env_file=None, insight_mode="llm")
    day = build_day(settings)

    with patch.object(httpx.AsyncClient, "post", new=AsyncMock(side_effect=httpx.ConnectError("refused"))):
        with pytest.raises(httpx.ConnectError):
            await InsightAgent(settings).run([day])


@pytest.mark.asyncio
async def test_auto_mode_batch_budget_caps_total_time_for_large_uploads():
    """A large upload in auto mode must not scale linearly with row count:
    once the batch time budget is spent, remaining rows skip the LLM
    entirely instead of each waiting out their own timeout."""
    settings = Settings(
        _env_file=None, insight_mode="auto",
        insight_batch_budget_seconds=1.2, ollama_timeout=5.0,
    )
    days = [
        build_day(settings, fc_name=f"FC-{i}").model_copy(update={"date": date(2026, 11, 1 + i)})
        for i in range(5)
    ]

    call_count = 0

    async def slow_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.5)
        return httpx.Response(
            200, json={"response": f"CM2 is {days[0].cm2_pct}% today, looking fine overall."},
            request=httpx.Request("POST", "http://test"),
        )

    with patch.object(httpx.AsyncClient, "post", new=AsyncMock(side_effect=slow_post)):
        start = time.monotonic()
        digests = await InsightAgent(settings).run(days)
        elapsed = time.monotonic() - start

    modes = [d.generation_mode for d in digests]
    assert modes[0] == "llm"  # first call had enough budget left and succeeded
    assert modes[1:] == ["rule"] * 4  # budget exhausted after that — no more LLM attempts
    assert call_count == 1  # confirms the remaining rows never even called out to Ollama
    assert elapsed < 2.5  # would be ~2.5s+ if every row waited out its own 0.5s call
    assert all(d.insight_text for d in digests)  # every row still got a usable insight
