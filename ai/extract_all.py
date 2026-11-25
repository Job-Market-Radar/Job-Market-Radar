import os
import time

import psycopg
from costs import cost_usd
from db import DATABASE_URL
from extract import (
    MODEL,
    SECONDS_BETWEEN_CALLS,
    build_prompt,
    extract_with_retry,
    new_usage,
)
from google import genai
from skills import normalize_skills

PROMPT_VERSION = "v3"

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
    remote = %(remote)s,
    salary_min = %(salary_min)s,
    salary_max = %(salary_max)s,
    currency = %(currency)s,
    salary_period = %(salary_period)s,
    extracted_at = now(),
    extraction_version = %(version)s
WHERE id = %(id)s
"""


if __name__ == "__main__":
    prompt_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "prompts", f"extract_{PROMPT_VERSION}.txt"
    )
    with open(prompt_path, encoding="utf-8") as f:
        template = f.read()
    client = genai.Client()
    usage = new_usage()  # time and tokens for the whole run

    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        rows = conn.execute(SELECT_TODO).fetchall()
        print(f"{len(rows)} postings to extract with {MODEL}")

        done = 0
        skipped = 0
        for number, (posting_id, source, title, description) in enumerate(rows, start=1):
            posting = {"id": posting_id, "source": source, "title": title, "description": description}
            print(f"[{number}/{len(rows)}] {posting_id}")
            result = extract_with_retry(client, build_prompt(template, posting), MODEL, usage)
            if result is None:
                skipped += 1
            else:
                fields = result.model_dump()
                fields["skills"] = normalize_skills(fields["skills"])
                if source == "remotive":
                    fields["remote"] = "remote"
                fields["id"] = posting_id
                fields["version"] = PROMPT_VERSION
                conn.execute(UPDATE_POSTING, fields)
                done += 1
            time.sleep(SECONDS_BETWEEN_CALLS)

    cost = cost_usd(MODEL, usage["input_tokens"], usage["output_tokens"])
    print(f"\nExtracted {done}, skipped {skipped}. Run it again to retry the skipped ones.")
    print(
        f"Usage: {usage['calls']} calls, {usage['input_tokens']:,} tokens in, "
        f"{usage['output_tokens']:,} out, {usage['seconds']:.0f} s of model time. "
        f"Paid-tier cost: ${cost:.4f}"
    )