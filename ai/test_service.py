import os

# CI has no .env: give the imports harmless fake values so they don't fail.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("GEMINI_API_KEY", "test-key")

import pytest
import service
from fastapi.testclient import TestClient
from google.genai.errors import APIError

JOB = {"id": "hackernews:1", "title": "AI Engineer", "company": "Acme", "skills": ["python", "docker"]}
MATCH = {
    "id": "hackernews:1",
    "title": "AI Engineer",
    "company": "Acme",
    "score": 0.8,
    "vector_score": 0.65,
    "skill_overlap": 0.5,
    "matching_skills": ["python"],
    "missing_skills": ["docker"],
}


class FakeResult:
    """What conn.execute(...) returns: answers set up by the test."""

    def __init__(self, one=None, rows=None):
        self.one = one
        self.rows = rows or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.rows


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def executemany(self, sql, rows):
        self.conn.saved_rows.extend(rows)


class FakeConn:
    """A pretend database: each execute() returns the next prepared answer, in order."""

    def __init__(self, results=()):
        self.results = list(results)
        self.saved_rows = []

    def execute(self, sql, params=None):
        return self.results.pop(0)

    def cursor(self, **kwargs):
        return FakeCursor(self)


@pytest.fixture
def client():
    service.app.dependency_overrides[service.get_client] = lambda: object()
    yield TestClient(service.app)
    service.app.dependency_overrides.clear()


def use_conn(conn):
    service.app.dependency_overrides[service.get_conn] = lambda: conn


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_similar_unknown_job_is_404(client):
    use_conn(FakeConn([FakeResult(one=None)]))
    response = client.get("/jobs/nope/similar")
    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}


def test_similar_returns_jobs(client, monkeypatch):
    use_conn(FakeConn([FakeResult(one=(1,))]))
    monkeypatch.setattr(service, "similar_jobs", lambda conn, job_id, limit: [{**MATCH, "score": 0.9}])
    monkeypatch.setattr(service, "get_jobs", lambda conn, ids: {"hackernews:1": JOB})
    response = client.get("/jobs/remotive:5/similar")
    assert response.status_code == 200
    assert response.json() == {"id": "remotive:5", "items": [{"score": 0.9, "job": JOB}]}


def test_similar_limit_too_big_is_422(client):
    use_conn(FakeConn())
    response = client.get("/jobs/x/similar?limit=51")
    assert response.status_code == 422


def test_stats_skills_counts_and_shares(client):
    use_conn(FakeConn([FakeResult(one=(10,)), FakeResult(rows=[("python", 4), ("docker", 2)])]))
    response = client.get("/stats/skills")
    assert response.status_code == 200
    assert response.json() == {
        "total_postings": 10,
        "items": [
            {"skill": "python", "count": 4, "share": 0.4},
            {"skill": "docker", "count": 2, "share": 0.2},
        ],
    }


def test_stats_skills_empty_database(client):
    use_conn(FakeConn([FakeResult(one=(0,)), FakeResult(rows=[])]))
    response = client.get("/stats/skills")
    assert response.json() == {"total_postings": 0, "items": []}


def test_match_cv_rejects_non_pdf(client):
    use_conn(FakeConn())
    response = client.post("/match-cv", files={"file": ("cv.txt", b"hello", "text/plain")})
    assert response.status_code == 400
    assert response.json() == {"detail": "File must be a PDF"}


def test_match_cv_rejects_big_file(client):
    use_conn(FakeConn())
    too_big = b"%PDF" + b"0" * service.MAX_CV_BYTES
    response = client.post("/match-cv", files={"file": ("cv.pdf", too_big, "application/pdf")})
    assert response.status_code == 413


def test_match_cv_unreadable_pdf_is_422(client):
    use_conn(FakeConn())
    response = client.post("/match-cv", files={"file": ("cv.pdf", b"%PDF-1.4 broken", "application/pdf")})
    assert response.status_code == 422


def test_match_cv_saves_and_returns_matches(client, monkeypatch):
    conn = FakeConn()
    use_conn(conn)
    monkeypatch.setattr(service, "pdf_text", lambda data: "my cv text")
    monkeypatch.setattr(service, "match_cv", lambda conn, client, text, limit: (["python"], [MATCH]))
    monkeypatch.setattr(service, "get_jobs", lambda conn, ids: {"hackernews:1": JOB})

    response = client.post("/match-cv", files={"file": ("cv.pdf", b"%PDF-fake", "application/pdf")})

    assert response.status_code == 200
    body = response.json()
    assert body["cv_skills"] == ["python"]
    assert body["items"][0]["rank"] == 1
    assert body["items"][0]["job"] == JOB
    # One cv_matches row was saved, with the same match_id the response returned.
    assert len(conn.saved_rows) == 1
    saved = conn.saved_rows[0]
    assert str(saved[0]) == body["match_id"]
    assert saved[1] == "hackernews:1"
    assert saved[2] == 1


def test_match_cv_gemini_busy_is_503(client, monkeypatch):
    use_conn(FakeConn())
    monkeypatch.setattr(service, "pdf_text", lambda data: "my cv text")

    def busy(*args, **kwargs):
        raise APIError(503, {"error": {"message": "overloaded", "status": "UNAVAILABLE"}})

    monkeypatch.setattr(service, "match_cv", busy)
    response = client.post("/match-cv", files={"file": ("cv.pdf", b"%PDF-fake", "application/pdf")})
    assert response.status_code == 503