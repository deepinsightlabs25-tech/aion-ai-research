"""
test_api.py — pytest integration tests for the FastAPI layer (api/server.py).

Uses FastAPI's TestClient (httpx-backed) — no real network calls, no Qdrant cloud.
The pipeline singleton is replaced by a stub via conftest.py's `api_client` fixture.

Scenarios covered:
  1. GET /health → 200 {"status": "ok"}
  2. POST /query — cache miss → 200, status="processing", task_id present.
  3. POST /query — cache hit  → 200, status="found", report present.
  4. GET /status — known task  → 200 with task dict.
  5. GET /status — unknown id  → 404.
  6. GET /report → 200, wraps list in {"reports": [...]}
  7. POST /cleanup → 200 {"status": "cleaned"}
  8. POST /query with empty body → 422 validation error.
"""

import pytest
from unittest.mock import MagicMock, patch

FAKE_REPORT = "# Test Report\n\nThis is a mocked research report."


# ---------------------------------------------------------------------------
# 1. Health check
# ---------------------------------------------------------------------------

def test_health(api_client):
    resp = api_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_auth_me(api_client):
    resp = api_client.get("/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sub"] == "dev-user"


# ---------------------------------------------------------------------------
# 2. POST /query — cache miss
# ---------------------------------------------------------------------------

def test_query_cache_miss(api_client, pipeline, in_memory_db):
    in_memory_db.search_query = MagicMock(return_value=None)

    resp = api_client.post("/query", json={"query": "AI in healthcare"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "processing"
    assert "task_id" in data
    assert data.get("report") is None


# ---------------------------------------------------------------------------
# 3. POST /query — cache hit
# ---------------------------------------------------------------------------

def test_query_cache_hit(api_client, pipeline, in_memory_db):
    in_memory_db.search_query = MagicMock(return_value=FAKE_REPORT)

    resp = api_client.post("/query", json={"query": "AI in healthcare"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "found"
    assert data["report"] == FAKE_REPORT
    assert data.get("task_id") is None


# ---------------------------------------------------------------------------
# 4. GET /status — known task
# ---------------------------------------------------------------------------

def test_get_status_known_task(api_client, pipeline, in_memory_db):
    in_memory_db.search_query = MagicMock(return_value=None)

    # Create a task via /query
    resp = api_client.post("/query", json={"query": "Robotics"})
    task_id = resp.json()["task_id"]

    # Mark it completed manually
    pipeline._tasks[task_id] = {"status": "completed", "report": FAKE_REPORT, "error": None}

    status_resp = api_client.get(f"/status?task_id={task_id}")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["status"] == "completed"
    assert data["report"] == FAKE_REPORT


# ---------------------------------------------------------------------------
# 5. GET /status — unknown task → 404
# ---------------------------------------------------------------------------

def test_get_status_unknown_task(api_client):
    resp = api_client.get("/status?task_id=nonexistent-id")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 6. GET /report
# ---------------------------------------------------------------------------

def test_get_all_reports(api_client, in_memory_db):
    fake = [{"id": "1", "query": "q1", "report": "r1"}]
    in_memory_db.get_reports = MagicMock(return_value=fake)

    resp = api_client.get("/report")
    assert resp.status_code == 200
    assert resp.json() == {"reports": fake}


# ---------------------------------------------------------------------------
# 7. POST /cleanup
# ---------------------------------------------------------------------------

def test_cleanup(api_client, pipeline, in_memory_db):
    in_memory_db.search_query = MagicMock(return_value=None)
    in_memory_db.cleanup = MagicMock(side_effect=lambda: in_memory_db.init_db())

    # Create a  task first
    api_client.post("/query", json={"query": "Cleanup test"})
    assert len(pipeline._tasks) > 0

    resp = api_client.post("/cleanup")
    assert resp.status_code == 200
    assert resp.json() == {"status": "cleaned"}
    assert len(pipeline._tasks) == 0


# ---------------------------------------------------------------------------
# 8. POST /query — validation error (empty body)
# ---------------------------------------------------------------------------

def test_query_missing_body(api_client):
    resp = api_client.post("/query", json={})
    assert resp.status_code == 422
