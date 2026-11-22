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


def similar_jobs(conn, posting_id: str, limit: int = 10) -> list[tuple]:
    """The postings whose embeddings are closest to this posting's embedding."""
    return conn.execute(SIMILAR, {"id": posting_id, "limit": limit}).fetchall()


if __name__ == "__main__":
    posting_id = sys.argv[1]
    with psycopg.connect(DATABASE_URL) as conn:
        target = conn.execute(
            "SELECT title, company FROM postings WHERE id = %s", (posting_id,)
        ).fetchone()
        if target is None:
            print(f"No posting with id {posting_id}")
            sys.exit(1)

        print(f"Jobs most similar to: {target[0]} @ {target[1]}\n")
        for pid, title, company, score in similar_jobs(conn, posting_id):
            print(f"{score:.2f}  {title} @ {company}  ({pid})")