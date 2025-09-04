import os
import tempfile
import pytest
from fastapi.testclient import TestClient

import main
import jobs

# Fixture: temporary DB for tests
@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    db_fd, db_path = tempfile.mkstemp()
    monkeypatch.setenv("DB_PATH", db_path)
    jobs.init_db()
    yield
    os.close(db_fd)
    os.remove(db_path)

client = TestClient(main.app)


def test_create_sleep_job():
    response = client.post("/jobs", json={"type": "sleep", "payload": {"seconds": 1}})
    assert response.status_code == 200 or response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] in ["queued", "succeeded"]


def test_get_nonexistent_job():
    response = client.get("/jobs/does-not-exist")
    assert response.status_code == 404


def test_create_duplicate_job():
    job = {"type": "sleep", "payload": {"seconds": 1}}
    r1 = client.post("/jobs", json=job)
    r2 = client.post("/jobs", json=job)
    assert r2.status_code == 200
    assert r2.json()["job_id"] == r1.json()["job_id"]


def test_cancel_job():
    job = {"type": "sleep", "payload": {"seconds": 2}}
    r = client.post("/jobs", json=job)
    job_id = r.json()["job_id"]

    cancel_resp = client.post(f"/jobs/{job_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["job_id"] == job_id


def test_list_jobs():
    # create a few jobs
    for _ in range(3):
        client.post("/jobs", json={"type": "sleep", "payload": {"seconds": 1}})
    r = client.get("/jobs?limit=2")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) <= 2
