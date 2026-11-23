import os
import time

import psycopg
from db import DATABASE_URL
from extract import SECONDS_BETWEEN_CALLS, build_prompt, extract_with_retry
from google import genai
from skills import normalize_skills

PROMPT_VERSION = "v3"

ADD_COLUMNS = """
ALTER TABLE postings
    ADD COLUMN IF NOT EXISTS work_mode TEXT,
    ADD COLUMN IF NOT EXISTS salary_period TEXT,
    ADD COLUMN IF NOT EXISTS extracted_at TIMESTAMPTZ
"""

SELECT_TODO = """
SELECT id, source, title, description
FROM postings
WHERE extracted_at IS NULL
ORDER BY id
"""

UPDATE_POSTING = """
UPDATE postings
SET skills = %(skills)s,
    seniority = %(seniority)s,
    work_mode = %(remote)s,
    salary_min = %(salary_min)s,
    salary_max = %(salary_max)s,
    currency = %(currency)s,
    salary_period = %(salary_period)s,
    extracted_at = now()
WHERE id = %(id)s
"""


if __name__ == "__main__":
    prompt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", f"extract_{PROMPT_VERSION}.txt")
    with open(prompt_path, encoding="utf-8") as f:        template = f.read()
    client = genai.Client()

    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        conn.execute(ADD_COLUMNS)
        rows = conn.execute(SELECT_TODO).fetchall()
        print(f"{len(rows)} postings to extract")

        done = 0
        skipped = 0
        for number, (posting_id, source, title, description) in enumerate(rows, start=1):
            posting = {"id": posting_id, "source": source, "title": title, "description": description}
            print(f"[{number}/{len(rows)}] {posting_id}")
            result = extract_with_retry(client, build_prompt(template, posting))
            if result is None:
                skipped += 1
            else:
                fields = result.model_dump()
                fields["skills"] = normalize_skills(fields["skills"])
                if source == "remotive":
                    fields["remote"] = "remote"
                fields["id"] = posting_id
                conn.execute(UPDATE_POSTING, fields)
                done += 1
            time.sleep(SECONDS_BETWEEN_CALLS)

    print(f"\nExtracted {done}, skipped {skipped}. Run it again to retry the skipped ones.")