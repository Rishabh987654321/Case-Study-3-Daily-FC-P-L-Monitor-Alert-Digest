"""Background processing: run the pipeline on an upload and persist results.

Runs as a FastAPI BackgroundTask after the upload response is returned, so it
gets its own DB session (request-scoped sessions are closed by then).
"""

import logging

from app.config import get_settings
from app.db import SessionLocal
from app.errors import ProcessingError
from app.models import AnomalyRow, DigestRow, FCDay, Upload, utcnow
from app.pipeline.notify_agent import render_digest_html
from app.pipeline.orchestrator import run_pipeline
from app.pipeline.report_writer import write_pnl_report
from app.services import storage

logger = logging.getLogger("pnl_monitor.processor")


async def process_upload(upload_id: str) -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        upload = db.get(Upload, upload_id)
        if upload is None:
            logger.warning("process_upload called for unknown upload_id=%s", upload_id)
            return

        file_path = storage.get_file_path(upload_id)
        if file_path is None:
            raise ProcessingError("Uploaded file not found on disk.")

        result = await run_pipeline(str(file_path), settings)

        # Paired by position, not by (fc_name, date) dict lookup: the ingest
        # agent allows duplicate (fc, date) rows (with a warning) and the
        # insight agent produces exactly one digest per pnl_data entry in
        # the same order, so positional pairing is the only way to keep
        # every duplicate row's own anomalies/digest instead of silently
        # collapsing them onto whichever row a dict key landed on last.
        fc_day_rows: list[FCDay] = []
        for p in result.pnl_data:
            row = FCDay(
                upload_id=upload_id, fc_name=p.fc_name, date=p.date,
                revenue=p.revenue, manpower_cost=p.manpower_cost, packaging_cost=p.packaging_cost,
                power_fuel=p.power_fuel, fc_rent=p.fc_rent, equipment_rentals=p.equipment_rentals,
                overheads=p.overheads, cm1=p.cm1, cm1_pct=p.cm1_pct, cm2=p.cm2, cm2_pct=p.cm2_pct,
                manpower_pct=p.manpower_pct, packaging_pct=p.packaging_pct,
                power_fuel_pct=p.power_fuel_pct, fc_rent_pct=p.fc_rent_pct,
                equipment_pct=p.equipment_pct, overheads_pct=p.overheads_pct,
                color_code=p.color_code.value if p.color_code else "GREEN",
            )
            db.add(row)
            fc_day_rows.append(row)
        db.flush()  # assign FCDay.id values before anomalies reference them

        delivery_lookup = {
            (item["fc_name"], item["date"]): item
            for item in result.delivery_results
            if item.get("type") != "cross_fc_summary"
        }

        total_anomalies = 0
        for i, p in enumerate(result.pnl_data):
            fc_day = fc_day_rows[i]
            digest = result.digests[i] if i < len(result.digests) else None
            if digest:
                fc_day.insight = digest.insight_text

            for a in p.anomalies:
                db.add(AnomalyRow(
                    upload_id=upload_id, fc_day_id=fc_day.id, fc_name=p.fc_name, date=p.date,
                    line_item=a.line_item, actual_pct=a.actual_pct, target_min=a.target_min,
                    target_max=a.target_max, deviation=a.deviation,
                    status=a.status.value, severity=a.severity.value,
                ))
                total_anomalies += 1

            if digest:
                delivery = delivery_lookup.get((p.fc_name, str(p.date)))
                db.add(DigestRow(
                    upload_id=upload_id, fc_name=p.fc_name, date=p.date,
                    color_code=digest.color_code.value, summary_text=digest.insight_text,
                    html_content=render_digest_html(p, digest), generation_mode=digest.generation_mode,
                    delivered_via=delivery["channel"] if delivery else None,
                    delivered_at=utcnow() if delivery else None,
                ))

        fc_names = {p.fc_name for p in result.pnl_data}
        dates = {p.date for p in result.pnl_data}
        upload.status = "completed"
        upload.fc_count = len(fc_names)
        upload.day_count = len(dates)
        upload.anomaly_count = total_anomalies
        upload.completed_at = utcnow()
        db.commit()

        try:
            write_pnl_report(
                result.pnl_data, result.anomalies, result.digests, str(storage.report_path(upload_id))
            )
        except Exception:
            logger.exception("Excel report generation failed for upload %s", upload_id)

    except Exception as exc:
        db.rollback()
        upload = db.get(Upload, upload_id)
        if upload:
            upload.status = "failed"
            upload.error_message = str(exc)
            upload.completed_at = utcnow()
            db.commit()
        logger.exception("Processing failed for upload %s", upload_id)
    finally:
        db.close()
