"""Orchestrator — chains Ingest -> Compute -> Detect -> Insight -> Notify.

If the Insight Agent fails outright (not just falls back to rules — an
actual exception, e.g. INSIGHT_MODE=llm with Ollama down), the pipeline
still returns the compute + detect results with empty digests, rather than
losing everything already computed.
"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.config import Settings
from app.pipeline.compute_agent import ComputeAgent
from app.pipeline.detect_agent import DetectAgent
from app.pipeline.ingest_agent import IngestAgent
from app.pipeline.insight_agent import InsightAgent
from app.pipeline.notify_agent import NotifyAgent
from app.types import FCDayDigest, FCDayPnL, FCDayRecord

logger = logging.getLogger("pnl_monitor.orchestrator")


@dataclass
class FlatAnomaly:
    fc_name: str
    date: str
    line_item: str
    actual_pct: float
    target_min: float
    target_max: float
    deviation: float
    status: str
    severity: str


@dataclass
class PipelineResult:
    records: list[FCDayRecord]
    pnl_data: list[FCDayPnL]
    anomalies: list[FlatAnomaly]
    digests: list[FCDayDigest]
    delivery_results: list[dict]
    timings: dict[str, float] = field(default_factory=dict)
    mode_counts: dict[str, int] = field(default_factory=dict)
    ingest_warnings: list[str] = field(default_factory=list)
    notify_warnings: list[str] = field(default_factory=list)


def _flatten_anomalies(pnl_data: list[FCDayPnL]) -> list[FlatAnomaly]:
    flat = []
    for p in pnl_data:
        for a in p.anomalies:
            flat.append(FlatAnomaly(
                fc_name=p.fc_name, date=str(p.date), line_item=a.line_item,
                actual_pct=a.actual_pct, target_min=a.target_min, target_max=a.target_max,
                deviation=a.deviation, status=a.status.value, severity=a.severity.value,
            ))
    return flat


async def run_pipeline(
    file_path: str, settings: Settings, digests_output_dir: Path | None = None,
) -> PipelineResult:
    timings: dict[str, float] = {}

    t0 = time.perf_counter()
    ingest_agent = IngestAgent()
    records = ingest_agent.run(file_path)
    timings["ingest"] = time.perf_counter() - t0
    logger.info("Ingest: %d records in %.3fs", len(records), timings["ingest"])

    t0 = time.perf_counter()
    pnl_data = ComputeAgent().run(records)
    timings["compute"] = time.perf_counter() - t0
    logger.info("Compute: %d FC-days in %.3fs", len(pnl_data), timings["compute"])

    t0 = time.perf_counter()
    pnl_data = DetectAgent(settings).run(pnl_data)
    timings["detect"] = time.perf_counter() - t0
    anomalies = _flatten_anomalies(pnl_data)
    logger.info("Detect: %d anomalies in %.3fs", len(anomalies), timings["detect"])

    t0 = time.perf_counter()
    digests: list[FCDayDigest] = []
    try:
        digests = await InsightAgent(settings).run(pnl_data)
    except Exception:
        logger.exception("Insight Agent failed; continuing with empty digests.")
    timings["insight"] = time.perf_counter() - t0
    mode_counts = {"llm": 0, "rule": 0}
    for d in digests:
        mode_counts[d.generation_mode] = mode_counts.get(d.generation_mode, 0) + 1
    logger.info(
        "Insight: %d digests in %.3fs (llm=%d, rule=%d)",
        len(digests), timings["insight"], mode_counts.get("llm", 0), mode_counts.get("rule", 0),
    )

    t0 = time.perf_counter()
    notify_agent = NotifyAgent(settings)
    delivery_results = notify_agent.run(
        pnl_data, digests, channel=settings.notify_channel, output_dir=digests_output_dir,
    )
    timings["notify"] = time.perf_counter() - t0
    logger.info("Notify: %d deliveries in %.3fs", len(delivery_results), timings["notify"])

    return PipelineResult(
        records=records,
        pnl_data=pnl_data,
        anomalies=anomalies,
        digests=digests,
        delivery_results=delivery_results,
        timings=timings,
        mode_counts=mode_counts,
        ingest_warnings=ingest_agent.warnings,
        notify_warnings=notify_agent.warnings,
    )
