import time

import pytest
from fastapi.testclient import TestClient

from app.main import app

CSV_CONTENT = (
    "FC Name,Date,Revenue,Manpower Cost,Packaging Cost,Power & Fuel,FC Rent,Equipment Rentals,Overheads\n"
    "FC-Test,2026-01-01,100000,25000,8000,5000,12000,4000,5000\n"
    "FC-Test,2026-01-02,110000,27000,8500,5200,12500,4100,5100\n"
)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def wait_for_completion(client: TestClient, upload_id: str, timeout: float = 15.0) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        resp = client.get(f"/api/upload/{upload_id}")
        data = resp.json()
        if data["status"] in ("completed", "failed"):
            return data
        time.sleep(0.1)
    raise TimeoutError(f"Upload {upload_id} did not finish processing within {timeout}s")


@pytest.fixture(scope="session")
def completed_upload(client: TestClient, sample_xlsx_path) -> str:
    with open(sample_xlsx_path, "rb") as f:
        resp = client.post(
            "/api/upload",
            files={"file": ("fc_daily_data.xlsx", f,
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"name": "Phase 2 Test Upload"},
        )
    assert resp.status_code == 201
    upload_id = resp.json()["upload_id"]
    data = wait_for_completion(client, upload_id)
    assert data["status"] == "completed", data
    return upload_id


# 1. POST valid CSV
def test_upload_valid_csv_returns_201(client: TestClient, tmp_path):
    path = tmp_path / "mini.csv"
    path.write_text(CSV_CONTENT)
    with open(path, "rb") as f:
        resp = client.post("/api/upload", files={"file": ("mini.csv", f, "text/csv")})
    assert resp.status_code == 201
    body = resp.json()
    assert body["upload_id"]
    assert body["status"] == "processing"
    assert body["filename"] == "mini.csv"


# 2. POST valid Excel
def test_upload_valid_excel_returns_201(client: TestClient, sample_xlsx_path):
    with open(sample_xlsx_path, "rb") as f:
        resp = client.post(
            "/api/upload",
            files={"file": ("fc_daily_data.xlsx", f,
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert resp.status_code == 201
    assert resp.json()["upload_id"]


# 3. POST wrong file type
def test_upload_wrong_file_type_returns_400(client: TestClient, tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("not a data file")
    with open(path, "rb") as f:
        resp = client.post("/api/upload", files={"file": ("notes.txt", f, "text/plain")})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_FILE"


# 4. POST empty file
def test_upload_empty_file_returns_400(client: TestClient, tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("")
    with open(path, "rb") as f:
        resp = client.post("/api/upload", files={"file": ("empty.csv", f, "text/csv")})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "NO_DATA"


# 5. GET upload status eventually completed
def test_get_upload_status_becomes_completed(client: TestClient, completed_upload: str):
    resp = client.get(f"/api/upload/{completed_upload}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["fc_count"] == 3
    assert body["day_count"] == 30
    assert body["anomaly_count"] == 45


# 6. GET dashboard
def test_dashboard_grid_structure(client: TestClient, completed_upload: str):
    resp = client.get(f"/api/upload/{completed_upload}/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["fcs"]) == 3
    assert len(body["dates"]) == 30
    assert set(body["grid"].keys()) == set(body["fcs"])
    total_cells = sum(len(v) for v in body["grid"].values())
    assert total_cells == 89  # 90 slots minus the planted missing FC-day


# 7. GET pnl paginated
def test_pnl_list_paginated(client: TestClient, completed_upload: str):
    resp = client.get(f"/api/upload/{completed_upload}/pnl", params={"page": 1, "page_size": 20})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 89
    assert len(body["items"]) == 20
    assert body["page"] == 1


# 8. GET pnl filtered by fc
def test_pnl_filtered_by_fc(client: TestClient, completed_upload: str):
    resp = client.get(f"/api/upload/{completed_upload}/pnl", params={"fc": "FC-Delhi", "page_size": 100})
    body = resp.json()
    assert body["total"] == 30
    assert all(item["fc_name"] == "FC-Delhi" for item in body["items"])


# 9. GET pnl filtered by color
def test_pnl_filtered_by_color_red(client: TestClient, completed_upload: str):
    resp = client.get(f"/api/upload/{completed_upload}/pnl", params={"color": "RED", "page_size": 100})
    body = resp.json()
    assert body["total"] == 5
    assert all(item["color_code"] == "RED" for item in body["items"])


# 10. GET anomalies
def test_anomalies_list(client: TestClient, completed_upload: str):
    resp = client.get(f"/api/upload/{completed_upload}/anomalies", params={"page_size": 100})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 45


# 11. GET anomalies filtered by severity
def test_anomalies_filtered_by_severity(client: TestClient, completed_upload: str):
    resp = client.get(
        f"/api/upload/{completed_upload}/anomalies", params={"severity": "HIGH", "page_size": 100}
    )
    body = resp.json()
    assert body["total"] > 0
    assert all(item["severity"] == "HIGH" for item in body["items"])


# 12. GET digests
def test_digests_list(client: TestClient, completed_upload: str):
    resp = client.get(f"/api/upload/{completed_upload}/digests")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["digests"]) == 89


# 13. GET export downloads xlsx
def test_export_downloads_xlsx(client: TestClient, completed_upload: str):
    resp = client.get(f"/api/upload/{completed_upload}/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert resp.content[:2] == b"PK"  # zip/xlsx magic bytes


def test_export_anomalies_csv(client: TestClient, completed_upload: str):
    resp = client.get(f"/api/upload/{completed_upload}/export/anomalies")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "Date,FC,Line Item" in resp.text


# 14. DELETE removes data
def test_delete_upload_removes_data(client: TestClient, tmp_path):
    path = tmp_path / "mini.csv"
    path.write_text(CSV_CONTENT)
    with open(path, "rb") as f:
        resp = client.post("/api/upload", files={"file": ("mini.csv", f, "text/csv")})
    upload_id = resp.json()["upload_id"]
    wait_for_completion(client, upload_id)

    del_resp = client.delete(f"/api/upload/{upload_id}")
    assert del_resp.status_code == 204

    get_resp = client.get(f"/api/upload/{upload_id}")
    assert get_resp.status_code == 404


# 15. GET nonexistent upload
def test_get_nonexistent_upload_returns_404(client: TestClient):
    resp = client.get("/api/upload/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


# 16. GET health
def test_health(client: TestClient):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# 17. GET config
def test_config(client: TestClient):
    resp = client.get("/api/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["targets"]["manpower"] == {"min": 20, "max": 28}
    assert body["cm1"] == {"min": 65, "max": 70}
    assert body["cm2"] == {"min": 15, "max": 30}
    assert body["cm_tolerance"] == 3


def test_list_uploads_paginated(client: TestClient, completed_upload: str):
    resp = client.get("/api/uploads", params={"page": 1, "page_size": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any(item["id"] == completed_upload for item in body["items"])


def test_single_fc_day_detail(client: TestClient, completed_upload: str):
    resp = client.get(f"/api/upload/{completed_upload}/pnl", params={"fc": "FC-Delhi", "date_from": "2026-11-05", "date_to": "2026-11-05"})
    fc_day_id = resp.json()["items"][0]["id"]

    detail_resp = client.get(f"/api/upload/{completed_upload}/pnl/{fc_day_id}")
    assert detail_resp.status_code == 200
    body = detail_resp.json()
    assert body["cm2_pct"] == 8.5
    assert body["color_code"] == "RED"
    assert len(body["anomalies"]) > 0
