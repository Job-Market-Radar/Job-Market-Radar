"""Grow the evaluation sample to a target size without touching postings already in it.

Usage: python ai\\eval\\add_to_sample.py 50
Safe to rerun: if the sample already has that many postings, it does nothing.
"""

import json
import os
import random
import sys

import psycopg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import DATABASE_URL

SAMPLE = os.path.join("ai", "eval", "sample.jsonl")
SEED = 43  # fixed so the pick is the same every time (pick_sample.py used 42)
REMOTIVE_SHARE = 5 / 30  # same mix as the first sample
SELECT_ALL = "SELECT id, source, title, company, description FROM postings ORDER BY id"


def read_jsonl(path: str) -> list[dict]:
    """Read a JSONL file: one JSON object per line."""
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


if __name__ == "__main__":
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    existing = read_jsonl(SAMPLE)
    needed = target - len(existing)
    if needed <= 0:
        print(f"Sample already has {len(existing)} postings, nothing to add.")
        sys.exit(0)

    taken = {p["id"] for p in existing}
    with psycopg.connect(DATABASE_URL) as conn:
        rows = conn.execute(SELECT_ALL).fetchall()
    columns = ["id", "source", "title", "company", "description"]
    candidates = [dict(zip(columns, row)) for row in rows if row[0] not in taken]
    remotive = [p for p in candidates if p["source"] == "remotive"]
    hackernews = [p for p in candidates if p["source"] == "hackernews"]

    picker = random.Random(SEED)
    remotive_count = min(round(needed * REMOTIVE_SHARE), len(remotive))
    picked = picker.sample(remotive, remotive_count) + picker.sample(hackernews, needed - remotive_count)

    with open(SAMPLE, "a", encoding="utf-8") as f:
        f.writelines(json.dumps(p, ensure_ascii=False) + "\n" for p in picked)

    print(f"Added {len(picked)} ({remotive_count} Remotive, {len(picked) - remotive_count} HN). "
          f"Sample now has {len(existing) + len(picked)} postings.")