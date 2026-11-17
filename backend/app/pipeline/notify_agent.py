"""Notify Agent — render and dispatch per-FC digests + a cross-FC daily summary.

File mode (default) writes HTML to data/digests/. Email mode sends via SMTP
and falls back to file mode (with a warning) if SMTP isn't configured or the
send fails. Dispatch never raises — it always returns a confirmation dict per
item, with status "delivered" or "failed".

Note on signature: this agent needs the full P&L numbers (revenue, cm1/cm2,
per-line %) to render the digest format from business_rules.md, not just the
lightweight FCDayDigest (insight text + anomalies). So it takes both
`pnl_data` and `digests` and joins them by (fc_name, date), rather than
`digests` alone.
"""

import smtplib
from collections import defaultdict
from email.mime.text import MIMEText
from pathlib import Path

from app.config import PROJECT_ROOT, Settings
from app.types import ColorCode, FCDayDigest, FCDayPnL

DEFAULT_DIGESTS_DIR = PROJECT_ROOT / "data" / "digests"

_COLOR_HEX = {
    ColorCode.RED: "#EF4444",
    ColorCode.YELLOW: "#F59E0B",
    ColorCode.GREEN: "#22C55E",
    ColorCode.BLUE: "#3B82F6",
}

_LINE_ITEMS = [
    ("Manpower", "manpower_pct"),
    ("Packaging", "packaging_pct"),
    ("Power & Fuel", "power_fuel_pct"),
    ("FC Rent", "fc_rent_pct"),
    ("Equipment", "equipment_pct"),
    ("Overheads", "overheads_pct"),
]


def _safe_fc(fc_name: str) -> str:
    return fc_name.replace(" ", "_").replace("/", "-")


def _line_status(pnl: FCDayPnL, label: str) -> str:
    canonical = {"Manpower": "Manpower Cost", "Packaging": "Packaging Cost",
                 "Equipment": "Equipment Rentals"}.get(label, label)
    for a in pnl.anomalies:
        if a.line_item == canonical:
            return a.status.value
    return "OK"


def render_digest_html(pnl: FCDayPnL, digest: FCDayDigest) -> str:
    color = _COLOR_HEX.get(digest.color_code, "#9CA3AF")
    rows = "".join(
        f"<tr><td>{label}</td><td>{getattr(pnl, attr)}%</td><td>{_line_status(pnl, label)}</td></tr>"
        for label, attr in _LINE_ITEMS
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{pnl.fc_name} — {pnl.date} Digest</title></head>
<body style="font-family: sans-serif; max-width: 640px; margin: 0 auto;">
  <h2>{pnl.fc_name} — Daily P&amp;L Digest</h2>
  <p>{pnl.date} | Status:
    <span style="background:{color}; color:white; padding:2px 10px; border-radius:4px;">{digest.color_code.value}</span>
  </p>
  <table style="width:100%; border-collapse: collapse;" border="1" cellpadding="6">
    <tr><td>Revenue</td><td colspan="2">₹{pnl.revenue:,.0f}</td></tr>
    <tr><td>CM1</td><td colspan="2">₹{pnl.cm1:,.0f} ({pnl.cm1_pct}%)</td></tr>
    <tr><td>CM2</td><td colspan="2">₹{pnl.cm2:,.0f} ({pnl.cm2_pct}%)</td></tr>
    <tr><th>Cost Line</th><th>% of Revenue</th><th>Status</th></tr>
    {rows}
  </table>
  <p>{digest.insight_text}</p>
  <p style="color:#888; font-size:12px;">Generated via {digest.generation_mode}.</p>
</body></html>"""


def render_summary_html(date, rows: list[tuple[FCDayPnL, FCDayDigest]]) -> str:
    body_rows = "".join(
        f"<tr><td>{pnl.fc_name}</td><td>{pnl.cm2_pct}%</td>"
        f"<td><span style=\"background:{_COLOR_HEX.get(digest.color_code, '#9CA3AF')}; "
        f"color:white; padding:2px 10px; border-radius:4px;\">{digest.color_code.value}</span></td>"
        f"<td>{len(pnl.anomalies)}</td></tr>"
        for pnl, digest in rows
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Cross-FC Summary — {date}</title></head>
<body style="font-family: sans-serif; max-width: 640px; margin: 0 auto;">
  <h2>Cross-FC Summary — {date}</h2>
  <table style="width:100%; border-collapse: collapse;" border="1" cellpadding="6">
    <tr><th>FC</th><th>CM2%</th><th>Status</th><th>Anomalies</th></tr>
    {body_rows}
  </table>
</body></html>"""


class NotifyAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.warnings: list[str] = []

    def run(
        self,
        pnl_data: list[FCDayPnL],
        digests: list[FCDayDigest],
        channel: str = "file",
        output_dir: Path | None = None,
    ) -> list[dict]:
        self.warnings = []
        out_dir = output_dir or DEFAULT_DIGESTS_DIR

        if channel not in ("file", "email", "webhook"):
            self.warnings.append(f"Unknown notify channel '{channel}'; falling back to file.")
            channel = "file"
        if channel == "webhook":
            self.warnings.append("Webhook channel not implemented; falling back to file.")
            channel = "file"

        pnl_map = {(p.fc_name, p.date): p for p in pnl_data}
        pairs = [(pnl_map[(d.fc_name, d.date)], d) for d in digests if (d.fc_name, d.date) in pnl_map]

        results: list[dict] = []
        if channel == "email" and not self.settings.smtp_user:
            self.warnings.append("SMTP not configured (no SMTP_USER); falling back to file.")
            channel = "file"

        if channel == "email":
            results.extend(self._send_email(pairs, out_dir))
        else:
            results.extend(self._write_files(pairs, out_dir))

        results.extend(self._write_summaries(pairs, out_dir, channel))
        return results

    def _write_files(self, pairs: list[tuple[FCDayPnL, FCDayDigest]], out_dir: Path) -> list[dict]:
        out_dir.mkdir(parents=True, exist_ok=True)
        results = []
        for pnl, digest in pairs:
            html = render_digest_html(pnl, digest)
            path = out_dir / f"{pnl.date}_{_safe_fc(pnl.fc_name)}.html"
            path.write_text(html, encoding="utf-8")
            results.append({
                "fc_name": pnl.fc_name, "date": str(pnl.date), "channel": "file",
                "status": "delivered", "path": str(path),
            })
        return results

    def _send_email(self, pairs: list[tuple[FCDayPnL, FCDayDigest]], out_dir: Path) -> list[dict]:
        recipients = [r.strip() for r in self.settings.digest_recipients.split(",") if r.strip()]
        if not recipients:
            self.warnings.append("No DIGEST_RECIPIENTS configured; falling back to file.")
            return self._write_files(pairs, out_dir)

        results = []
        try:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.settings.smtp_user, self.settings.smtp_password)
                for pnl, digest in pairs:
                    html = render_digest_html(pnl, digest)
                    msg = MIMEText(html, "html")
                    msg["Subject"] = f"FC P&L Digest — {pnl.fc_name} — {pnl.date} [{digest.color_code.value}]"
                    msg["From"] = self.settings.smtp_user
                    msg["To"] = ", ".join(recipients)
                    server.sendmail(self.settings.smtp_user, recipients, msg.as_string())
                    results.append({
                        "fc_name": pnl.fc_name, "date": str(pnl.date), "channel": "email",
                        "status": "delivered", "recipients": recipients,
                    })
        except Exception as exc:
            self.warnings.append(f"Email delivery failed ({exc}); falling back to file.")
            return self._write_files(pairs, out_dir)
        return results

    def _write_summaries(
        self, pairs: list[tuple[FCDayPnL, FCDayDigest]], out_dir: Path, channel: str,
    ) -> list[dict]:
        by_date: dict = defaultdict(list)
        for pnl, digest in pairs:
            by_date[pnl.date].append((pnl, digest))

        out_dir.mkdir(parents=True, exist_ok=True)
        results = []
        for day, rows in by_date.items():
            html = render_summary_html(day, sorted(rows, key=lambda pd: pd[0].fc_name))
            path = out_dir / f"{day}_summary.html"
            path.write_text(html, encoding="utf-8")
            results.append({
                "fc_name": "ALL", "date": str(day), "channel": "file",
                "status": "delivered", "path": str(path), "type": "cross_fc_summary",
            })
        return results
