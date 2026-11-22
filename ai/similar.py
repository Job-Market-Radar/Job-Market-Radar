import sys

import psycopg
from db import DATABASE_URL

SIMILAR = """
SELECT p.id, p.title, p.company, 1 - (e.embedding <=> t.embedding) AS score
FROM posting_embeddings e
JOIN postings p ON p.id = e.posting_id
CROSS JOIN (SELECT embedding FROM posting_embeddings WHERE posting_id = %(id)s) t
WHERE e.posting_id <> %(id)s
ORDER BY e.embedding <=> t.embedding
LIMIT %(limit)s
"""


def similar_jobs(conn, posting_id: str, limit: int = 10) -> list[dict]:
    """The postings whose embeddings are closest to this posting's, best first."""
    rows = conn.execute(SIMILAR, {"id": posting_id, "limit": limit}).fetchall()
    return [{"id": r[0], "title": r[1], "company": r[2], "score": r[3]} for r in rows]


if __name__ == "__main__":
    with psycopg.connect(DATABASE_URL) as conn:
        for job in similar_jobs(conn, sys.argv[1]):
            print(f"{job['score']:.2f}  {job['title']} @ {job['company']}")