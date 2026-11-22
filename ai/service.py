import io
import uuid
from functools import lru_cache
from typing import Annotated

import psycopg
from db import DATABASE_URL
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from google import genai
from google.genai.errors import APIError
from match_cv import match_cv
from psycopg.rows import dict_row
from pypdf import PdfReader
from pypdf.errors import PyPdfError
from similar import similar_jobs

MAX_CV_BYTES = 5 * 1024 * 1024  # 5 MB, from the contract

# The job posting fields every response includes (contract §2).
JOB_COLUMNS = (
    "id, source, url, title, company, location, remote, posted_at, description, "
    "skills, seniority, salary_min, salary_max, currency, salary_period"
)

INSERT_MATCH = """
INSERT INTO cv_matches
    (match_id, posting_id, rank, score, vector_score, skill_overlap, matching_skills, missing_skills)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""

# Postings that pass the optional filters. A NULL filter means "don't filter on this".
FILTERED = """
FROM postings
WHERE extracted_at IS NOT NULL
  AND (%(since)s::date IS NULL OR posted_at >= %(since)s::date)
  AND (%(seniority)s::text IS NULL OR seniority = %(seniority)s)
"""
COUNT_POSTINGS = "SELECT count(*) " + FILTERED
TOP_SKILLS = (
    "SELECT skill, count(*) AS count "
    + FILTERED.replace("FROM postings", "FROM postings, unnest(skills) AS skill")
    + "GROUP BY skill ORDER BY count DESC, skill LIMIT %(limit)s"
)

app = FastAPI(title="Job Market Radar AI service")


def get_conn():
    """One database connection per request; saved changes are committed when the request ends."""
    with psycopg.connect(DATABASE_URL) as conn:
        yield conn


@lru_cache
def get_client():
    """One Gemini client for the whole service, created the first time it's needed."""
    return genai.Client()


# Shorthands for "FastAPI, give this endpoint a connection / the Gemini client".
Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Client = Annotated[genai.Client, Depends(get_client)]


def get_jobs(conn, ids: list[str]) -> dict[str, dict]:
    """Full job postings for these ids, keyed by id."""
    if not ids:
        return {}
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(f"SELECT {JOB_COLUMNS} FROM postings WHERE id = ANY(%s)", (ids,)).fetchall()
    return {row["id"]: row for row in rows}


def pdf_text(data: bytes) -> str:
    """The text of a PDF held in memory, or "" if it can't be read."""
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except (PyPdfError, ValueError, KeyError, TypeError):  # errors a broken PDF can cause
        return ""


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/jobs/{job_id}/similar")
def similar(job_id: str, conn: Conn, limit: Annotated[int, Query(ge=1, le=50)] = 10):
    if not conn.execute("SELECT 1 FROM postings WHERE id = %s", (job_id,)).fetchone():
        raise HTTPException(status_code=404, detail="Job not found")
    matches = similar_jobs(conn, job_id, limit)
    jobs = get_jobs(conn, [m["id"] for m in matches])
    return {"id": job_id, "items": [{"score": m["score"], "job": jobs[m["id"]]} for m in matches]}


@app.get("/stats/skills")
def stats_skills(
    conn: Conn,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    since: str | None = None,
    seniority: str | None = None,
):
    params = {"since": since, "seniority": seniority, "limit": limit}
    total = conn.execute(COUNT_POSTINGS, params).fetchone()[0]
    rows = conn.execute(TOP_SKILLS, params).fetchall()
    items = [
        {"skill": skill, "count": count, "share": round(count / total, 3) if total else 0.0}
        for skill, count in rows
    ]
    return {"total_postings": total, "items": items}


@app.post("/match-cv")
def match_cv_endpoint(
    file: Annotated[UploadFile, File()],
    conn: Conn,
    client: Client,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
):
    data = file.file.read(MAX_CV_BYTES + 1)
    if len(data) > MAX_CV_BYTES:
        raise HTTPException(status_code=413, detail="File too large")
    if not data.startswith(b"%PDF"):  # every real PDF starts with these bytes
        raise HTTPException(status_code=400, detail="File must be a PDF")
    text = pdf_text(data)
    if not text:
        raise HTTPException(status_code=422, detail="Could not read text from the PDF")

    try:
        cv_skills, matches = match_cv(conn, client, text, limit)
    except APIError:
        raise HTTPException(status_code=503, detail="The AI model is busy, try again in a minute") from None

    match_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.executemany(
            INSERT_MATCH,
            [
                (match_id, m["id"], rank, m["score"], m["vector_score"], m["skill_overlap"],
                 m["matching_skills"], m["missing_skills"])
                for rank, m in enumerate(matches, start=1)
            ],
        )

    jobs = get_jobs(conn, [m["id"] for m in matches])
    items = [
        {
            "rank": rank,
            "score": m["score"],
            "vector_score": m["vector_score"],
            "skill_overlap": m["skill_overlap"],
            "matching_skills": m["matching_skills"],
            "missing_skills": m["missing_skills"],
            "job": jobs[m["id"]],
        }
        for rank, m in enumerate(matches, start=1)
    ]
    return {"match_id": str(match_id), "cv_skills": cv_skills, "items": items}