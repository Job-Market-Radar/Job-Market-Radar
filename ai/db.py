import os

import psycopg
from clean import (
    clean_hn,
    clean_remotive,
    latest_raw_file,
    load_json,
    remove_duplicates,
)
from dotenv import load_dotenv
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb

load_dotenv()
# Locally: one DATABASE_URL. On AWS: four separate DB_* settings from Secrets Manager.
DATABASE_URL = os.environ.get("DATABASE_URL") or make_conninfo(
    host=os.environ["DB_HOST"],
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    port=os.environ.get("DB_PORT", "5432"),
)

CREATE_TABLES = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS raw_postings (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    data        JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS postings (
    id                  TEXT PRIMARY KEY,
    source              TEXT NOT NULL,
    url                 TEXT NOT NULL,
    title               TEXT,
    company             TEXT,
    location            TEXT,
    remote              TEXT NOT NULL DEFAULT 'unknown',
    posted_at           TIMESTAMPTZ,
    description         TEXT,
    skills              TEXT[] NOT NULL DEFAULT '{}',
    seniority           TEXT,
    salary_min          INTEGER,
    salary_max          INTEGER,
    currency            TEXT,
    salary_period       TEXT,
    extracted_at        TIMESTAMPTZ,
    extraction_version  TEXT
);

CREATE INDEX IF NOT EXISTS postings_skills_idx ON postings USING gin (skills);

CREATE TABLE IF NOT EXISTS posting_embeddings (
    posting_id  TEXT PRIMARY KEY REFERENCES postings(id) ON DELETE CASCADE,
    model       TEXT NOT NULL,
    embedding   vector(768) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS posting_embeddings_hnsw_idx
    ON posting_embeddings USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS cv_matches (
    id               BIGSERIAL PRIMARY KEY,
    match_id         UUID NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    posting_id       TEXT NOT NULL REFERENCES postings(id) ON DELETE CASCADE,
    rank             SMALLINT NOT NULL,
    score            REAL NOT NULL,
    vector_score     REAL NOT NULL,
    skill_overlap    REAL NOT NULL,
    matching_skills  TEXT[] NOT NULL,
    missing_skills   TEXT[] NOT NULL
);
"""

INSERT_RAW = """
INSERT INTO raw_postings (id, source, data)
VALUES (%s, %s, %s)
ON CONFLICT (id) DO UPDATE
SET data = EXCLUDED.data, fetched_at = now()
WHERE raw_postings.data IS DISTINCT FROM EXCLUDED.data
"""

# Upsert: new postings are added; changed ones get their source fields updated.
# The extracted fields (skills, seniority, salary...) are never overwritten here.
INSERT_POSTING = """
INSERT INTO postings (id, source, url, title, company, location, remote, posted_at,
                      description, skills, seniority, salary_min, salary_max, currency)
VALUES (%(id)s, %(source)s, %(url)s, %(title)s, %(company)s, %(location)s, %(remote)s,
        %(posted_at)s, %(description)s, %(skills)s, %(seniority)s, %(salary_min)s,
        %(salary_max)s, %(currency)s)
ON CONFLICT (id) DO UPDATE SET
    url = EXCLUDED.url,
    title = EXCLUDED.title,
    company = EXCLUDED.company,
    location = EXCLUDED.location,
    posted_at = EXCLUDED.posted_at,
    description = EXCLUDED.description,
    -- New text means the old extraction may be wrong: let extract_all.py redo it.
    extracted_at = CASE
        WHEN postings.description IS DISTINCT FROM EXCLUDED.description THEN NULL
        ELSE postings.extracted_at
    END
WHERE (postings.url, postings.title, postings.company, postings.location,
       postings.posted_at, postings.description)
      IS DISTINCT FROM
      (EXCLUDED.url, EXCLUDED.title, EXCLUDED.company, EXCLUDED.location,
       EXCLUDED.posted_at, EXCLUDED.description)
"""


def create_tables(conn) -> None:
    """Create the tables if they don't exist yet."""
    conn.execute(CREATE_TABLES)


def insert_raw(conn, source: str, items: list[dict]) -> int:
    """Store raw items untouched; skip ones already stored. Return how many were new."""
    added = 0
    for item in items:
        result = conn.execute(INSERT_RAW, (f"{source}:{item['id']}", source, Jsonb(item)))
        added = added + result.rowcount
    return added


def insert_postings(conn, postings: list[dict]) -> int:
    """Store clean postings; skip ones already stored. Return how many were new."""
    added = 0
    for posting in postings:
        result = conn.execute(INSERT_POSTING, posting)
        added = added + result.rowcount
    return added


if __name__ == "__main__":
    remotive_raw = load_json(latest_raw_file("remotive"))
    hn_raw = load_json(latest_raw_file("hackernews"))

    postings = [clean_remotive(job) for job in remotive_raw] + [clean_hn(post) for post in hn_raw]
    postings = remove_duplicates(postings)

    with psycopg.connect(DATABASE_URL) as conn:
        create_tables(conn)
        raw_added = insert_raw(conn, "remotive", remotive_raw) + insert_raw(conn, "hackernews", hn_raw)
        added = insert_postings(conn, postings)
        total = conn.execute("SELECT count(*) FROM postings").fetchone()[0]

    print(f"Raw: {raw_added} new or changed")
    print(f"Postings: {added} new or changed, {total} total in the database")