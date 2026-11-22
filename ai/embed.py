import time

import psycopg
from db import DATABASE_URL
from google import genai
from google.genai import errors, types

MODEL = "gemini-embedding-001"
DIMENSIONS = 768
BATCH_SIZE = 20
MAX_CHARS = 6000
SECONDS_BETWEEN_CALLS = 5

SELECT_TODO = """
SELECT p.id, p.source, p.title, p.description
FROM postings p
LEFT JOIN posting_embeddings e ON e.posting_id = p.id
WHERE e.posting_id IS NULL
ORDER BY p.id
"""

UPSERT_EMBEDDING = """
INSERT INTO posting_embeddings (posting_id, model, embedding)
VALUES (%s, %s, %s::vector)
ON CONFLICT (posting_id) DO UPDATE
SET model = EXCLUDED.model, embedding = EXCLUDED.embedding, created_at = now()
"""


def posting_text(source: str, title: str | None, description: str | None) -> str:
    """The text that gets turned into an embedding, cut to a safe length."""
    text = description or ""
    if source == "remotive":
        text = f"{title or ''}\n\n{text}"
    return text[:MAX_CHARS]


def embed_texts(client, texts: list[str], task_type: str) -> list[list[float]]:
    """Turn a list of texts into a list of embeddings: one list of numbers per text."""
    response = client.models.embed_content(
        model=MODEL,
        contents=texts,
        config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=DIMENSIONS),
    )
    return [embedding.values for embedding in response.embeddings]


def to_pgvector(values: list[float]) -> str:
    """pgvector reads a vector written as text, like [0.1,0.2,0.3]."""
    return "[" + ",".join(str(v) for v in values) + "]"


if __name__ == "__main__":
    client = genai.Client()
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        rows = conn.execute(SELECT_TODO).fetchall()
        print(f"{len(rows)} postings to embed")

        for start in range(0, len(rows), BATCH_SIZE):
            batch = rows[start:start + BATCH_SIZE]
            texts = [posting_text(source, title, description) for _, source, title, description in batch]
            try:
                vectors = embed_texts(client, texts, "RETRIEVAL_DOCUMENT")
            except errors.APIError as error:
                print(f"  batch at {start}: API error {error.code}, skipping it for now")
                time.sleep(30)
                continue
            for (posting_id, _, _, _), values in zip(batch, vectors):
                conn.execute(UPSERT_EMBEDDING, (posting_id, MODEL, to_pgvector(values)))
            print(f"  embedded {start + len(batch)}/{len(rows)}")
            time.sleep(SECONDS_BETWEEN_CALLS)

    print("Done. Run it again to retry any skipped batches.")