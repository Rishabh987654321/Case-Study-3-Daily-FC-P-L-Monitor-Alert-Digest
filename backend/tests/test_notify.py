from datetime import date

from app.config import Settings
from app.pipeline.compute_agent import ComputeAgent
from app.pipeline.detect_agent import DetectAgent
from app.pipeline.notify_agent import NotifyAgent
from app.types import FCDayDigest, FCDayRecord


def settings() -> Settings:
    return Settings(_env_file=None)


def make_pnl(fc_name="FC-Delhi", day=date(2026, 11, 1)):
    record = FCDayRecord(
        fc_name=fc_name, date=day, revenue=213400,
        manpower_cost=59199, packaging_cost=20471, power_fuel=14308,
        fc_rent=31279, equipment_rentals=10123, overheads=14102,
    )
    pnl = ComputeAgent().compute_one(record)
    return DetectAgent(settings()).detect_one(pnl)


def make_digest(pnl, text="All good, CM2 within target.") -> FCDayDigest:
    return FCDayDigest(
        fc_name=pnl.fc_name, date=pnl.date, color_code=pnl.color_code,
        anomalies=pnl.anomalies, insight_text=text, generation_mode="rule",
    )


def test_file_mode_creates_html_with_correct_content_and_location(tmp_path):
    pnl = make_pnl()
    digest = make_digest(pnl, text="Insight: everything looks healthy today.")
    agent = NotifyAgent(settings())
    results = agent.run([pnl], [digest], channel="file", output_dir=tmp_path)

    fc_result = next(r for r in results if r.get("type") != "cross_fc_summary")
    path = tmp_path / f"{pnl.date}_{pnl.fc_name}.html"
    assert path.exists()
    content = path.read_text()
    assert "Insight: everything looks healthy today." in content
    assert f"₹{pnl.revenue:,.0f}" in content
    assert str(pnl.cm2_pct) in content
    assert fc_result["status"] == "delivered"


def test_cross_fc_summary_generated(tmp_path):
    pnl1 = make_pnl(fc_name="FC-Delhi")
    pnl2 = make_pnl(fc_name="FC-Mumbai")
    d1, d2 = make_digest(pnl1), make_digest(pnl2)
    agent = NotifyAgent(settings())
    results = agent.run([pnl1, pnl2], [d1, d2], channel="file", output_dir=tmp_path)

    summary_result = next(r for r in results if r.get("type") == "cross_fc_summary")
    summary_path = tmp_path / f"{pnl1.date}_summary.html"
    assert summary_path.exists()
    content = summary_path.read_text()
    assert "FC-Delhi" in content
    assert "FC-Mumbai" in content
    assert summary_result["status"] == "delivered"


def test_invalid_channel_falls_back_to_file_with_warning(tmp_path):
    pnl = make_pnl()
    digest = make_digest(pnl)
    agent = NotifyAgent(settings())
    results = agent.run([pnl], [digest], channel="carrier_pigeon", output_dir=tmp_path)

    assert any("Unknown notify channel" in w for w in agent.warnings)
    assert all(r["channel"] == "file" for r in results)
    path = tmp_path / f"{pnl.date}_{pnl.fc_name}.html"
    assert path.exists()


def test_email_without_smtp_config_falls_back_to_file(tmp_path):
    pnl = make_pnl()
    digest = make_digest(pnl)
    agent = NotifyAgent(settings())  # smtp_user is empty by default
    results = agent.run([pnl], [digest], channel="email", output_dir=tmp_path)

    assert any("SMTP not configured" in w for w in agent.warnings)
    fc_result = next(r for r in results if r.get("type") != "cross_fc_summary")
    assert fc_result["channel"] == "file"


def test_digest_mentions_anomalous_line_item_status(tmp_path):
    record = FCDayRecord(
        fc_name="FC-Delhi", date=date(2026, 11, 5), revenue=237400,
        manpower_cost=85464, packaging_cost=22553, power_fuel=26114,
        fc_rent=54602, equipment_rentals=11870, overheads=16618,
    )
    pnl = DetectAgent(settings()).detect_one(ComputeAgent().compute_one(record))
    digest = make_digest(pnl, text="CM2 crashed to 8.5%.")
    agent = NotifyAgent(settings())
    agent.run([pnl], [digest], channel="file", output_dir=tmp_path)
    content = (tmp_path / f"{pnl.date}_{pnl.fc_name}.html").read_text()
    assert "RED" in content
    assert "BREACH_HIGH" in content
