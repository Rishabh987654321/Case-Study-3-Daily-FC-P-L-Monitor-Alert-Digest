import pandas as pd
import pytest

from app.errors import IngestError
from app.pipeline.ingest_agent import IngestAgent


def test_parses_sample_xlsx(sample_xlsx_path):
    agent = IngestAgent()
    records = agent.run(str(sample_xlsx_path))
    assert len(records) == 89  # 3 FCs x 30 days minus 1 planted missing day
    fc_names = {r.fc_name for r in records}
    assert fc_names == {"FC-Delhi", "FC-Mumbai", "FC-Bangalore"}
    # sorted by (date, fc_name)
    pairs = [(r.date, r.fc_name) for r in records]
    assert pairs == sorted(pairs)


def test_parses_csv(tmp_path):
    csv_path = tmp_path / "data.csv"
    csv_path.write_text(
        "FC Name,Date,Revenue,Manpower Cost,Packaging Cost,Power & Fuel,FC Rent,Equipment Rentals,Overheads\n"
        "FC-Test,2026-01-01,100000,25000,8000,5000,12000,4000,5000\n"
    )
    agent = IngestAgent()
    records = agent.run(str(csv_path))
    assert len(records) == 1
    r = records[0]
    assert r.fc_name == "FC-Test"
    assert r.revenue == 100000
    assert r.manpower_cost == 25000


def test_handles_missing_optional_columns(tmp_path):
    csv_path = tmp_path / "data.csv"
    csv_path.write_text(
        "FC,Date,Revenue,Manpower\nFC-Test,2026-01-01,100000,25000\n"
    )
    agent = IngestAgent()
    records = agent.run(str(csv_path))
    assert len(records) == 1
    assert records[0].packaging_cost == 0.0
    assert records[0].overheads == 0.0
    assert any("not found" in w for w in agent.warnings)


def test_empty_file_raises_clear_error(tmp_path):
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("")
    agent = IngestAgent()
    with pytest.raises(IngestError):
        agent.run(str(csv_path))


def test_headers_only_returns_empty_list_with_warning(tmp_path):
    csv_path = tmp_path / "headers_only.csv"
    csv_path.write_text("FC,Date,Revenue,Manpower,Packaging,Power,Rent,Equipment,Overheads\n")
    agent = IngestAgent()
    records = agent.run(str(csv_path))
    assert records == []
    assert any("no data rows" in w for w in agent.warnings)


def test_missing_required_column_raises(tmp_path):
    csv_path = tmp_path / "no_revenue.csv"
    csv_path.write_text("FC,Date,Manpower\nFC-Test,2026-01-01,25000\n")
    agent = IngestAgent()
    with pytest.raises(IngestError):
        agent.run(str(csv_path))


def test_skips_total_rows(tmp_path):
    csv_path = tmp_path / "data.csv"
    csv_path.write_text(
        "FC,Date,Revenue,Manpower,Packaging,Power,Rent,Equipment,Overheads\n"
        "FC-Test,2026-01-01,100000,25000,8000,5000,12000,4000,5000\n"
        "Total,,100000,25000,8000,5000,12000,4000,5000\n"
    )
    agent = IngestAgent()
    records = agent.run(str(csv_path))
    assert len(records) == 1
    assert any("summary/total" in w for w in agent.warnings)


def test_skips_rows_with_missing_revenue(tmp_path):
    csv_path = tmp_path / "data.csv"
    csv_path.write_text(
        "FC,Date,Revenue,Manpower,Packaging,Power,Rent,Equipment,Overheads\n"
        "FC-A,2026-01-01,100000,25000,8000,5000,12000,4000,5000\n"
        "FC-B,2026-01-01,,25000,8000,5000,12000,4000,5000\n"
    )
    agent = IngestAgent()
    records = agent.run(str(csv_path))
    assert len(records) == 1
    assert any("missing/unparsable revenue" in w for w in agent.warnings)


def test_unsupported_file_type_raises(tmp_path):
    path = tmp_path / "data.txt"
    path.write_text("hello")
    agent = IngestAgent()
    with pytest.raises(IngestError):
        agent.run(str(path))


def test_file_not_found_raises():
    agent = IngestAgent()
    with pytest.raises(IngestError):
        agent.run("does/not/exist.csv")


def test_txt_content_renamed_to_xlsx_raises_clean_ingest_error(tmp_path):
    path = tmp_path / "fake.xlsx"
    path.write_text("this is not a real excel file, just plain text\n")
    agent = IngestAgent()
    with pytest.raises(IngestError):
        agent.run(str(path))


def test_semicolon_delimited_csv_is_detected(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text(
        "FC;Date;Revenue;Manpower;Packaging;Power;Rent;Equipment;Overheads\n"
        "FC-Test;2026-01-01;100000;25000;8000;5000;12000;4000;5000\n"
    )
    records = IngestAgent().run(str(path))
    assert len(records) == 1
    assert records[0].revenue == 100000


def test_tab_delimited_csv_is_detected(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text(
        "FC\tDate\tRevenue\tManpower\tPackaging\tPower\tRent\tEquipment\tOverheads\n"
        "FC-Test\t2026-01-01\t100000\t25000\t8000\t5000\t12000\t4000\t5000\n"
    )
    records = IngestAgent().run(str(path))
    assert len(records) == 1
    assert records[0].revenue == 100000


def test_mixed_date_formats_all_parse_correctly(tmp_path):
    from datetime import date

    path = tmp_path / "data.csv"
    path.write_text(
        "FC,Date,Revenue,Manpower,Packaging,Power,Rent,Equipment,Overheads\n"
        "FC-ISO,2026-11-05,100000,25000,8000,5000,12000,4000,5000\n"       # ISO
        "FC-SLASH,05/11/2026,100000,25000,8000,5000,12000,4000,5000\n"     # day-first slash
        "FC-NAMED,1-Nov-2026,100000,25000,8000,5000,12000,4000,5000\n"     # named month
    )
    records = {r.fc_name: r.date for r in IngestAgent().run(str(path))}
    assert records["FC-ISO"] == date(2026, 11, 5)
    assert records["FC-SLASH"] == date(2026, 11, 5)  # day-first, not US month-first
    assert records["FC-NAMED"] == date(2026, 11, 1)


def test_non_numeric_cost_value_skips_row_with_warning(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text(
        "FC,Date,Revenue,Manpower,Packaging,Power,Rent,Equipment,Overheads\n"
        "FC-A,2026-01-01,100000,25000,8000,5000,12000,4000,5000\n"
        "FC-B,2026-01-02,100000,pending,8000,5000,12000,4000,5000\n"
    )
    agent = IngestAgent()
    records = agent.run(str(path))
    assert len(records) == 1
    assert records[0].fc_name == "FC-A"
    assert any("non-numeric" in w for w in agent.warnings)


def test_blank_cost_cell_defaults_to_zero_not_skipped(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text(
        "FC,Date,Revenue,Manpower,Packaging,Power,Rent,Equipment,Overheads\n"
        "FC-A,2026-01-02,100000,,8000,5000,12000,4000,5000\n"
    )
    agent = IngestAgent()
    records = agent.run(str(path))
    assert len(records) == 1
    assert records[0].manpower_cost == 0.0


def test_duplicate_fc_date_rows_both_kept_with_warning(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text(
        "FC,Date,Revenue,Manpower,Packaging,Power,Rent,Equipment,Overheads\n"
        "FC-A,2026-01-01,100000,25000,8000,5000,12000,4000,5000\n"
        "FC-A,2026-01-01,110000,26000,8200,5100,12100,4100,5100\n"
    )
    agent = IngestAgent()
    records = agent.run(str(path))
    assert len(records) == 2
    assert any("duplicate" in w.lower() for w in agent.warnings)


def test_single_fc_single_day_file_works(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text(
        "FC,Date,Revenue,Manpower,Packaging,Power,Rent,Equipment,Overheads\n"
        "FC-Solo,2026-01-01,100000,25000,8000,5000,12000,4000,5000\n"
    )
    records = IngestAgent().run(str(path))
    assert len(records) == 1


def test_very_large_revenue_no_overflow(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text(
        "FC,Date,Revenue,Manpower,Packaging,Power,Rent,Equipment,Overheads\n"
        "FC-Big,2026-01-01,100000000,27000000,9000000,6000000,14000000,4500000,6500000\n"
    )
    records = IngestAgent().run(str(path))
    assert records[0].revenue == 100_000_000


def test_picks_daily_data_sheet_over_other_sheets(tmp_path):
    xlsx_path = tmp_path / "multi_sheet.xlsx"
    daily = pd.DataFrame({
        "FC": ["FC-Test"], "Date": ["2026-01-01"], "Revenue": [100000],
        "Manpower": [25000], "Packaging": [8000], "Power": [5000],
        "Rent": [12000], "Equipment": [4000], "Overheads": [5000],
    })
    other = pd.DataFrame({"Notes": ["irrelevant sheet"]})
    with pd.ExcelWriter(xlsx_path) as writer:
        other.to_excel(writer, sheet_name="Target Ranges", index=False)
        daily.to_excel(writer, sheet_name="Daily Data", index=False)
    agent = IngestAgent()
    records = agent.run(str(xlsx_path))
    assert len(records) == 1
    assert records[0].fc_name == "FC-Test"
