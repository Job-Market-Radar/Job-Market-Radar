"""Re-apply the current skill aliases to skills already stored in the database.

Run it after adding aliases to skills.py. Safe to run again: unchanged postings are left alone.
"""

import psycopg
from db import DATABASE_URL
from skills import normalize_skills

SELECT_SKILLS = "SELECT id, skills FROM postings WHERE cardinality(skills) > 0"
UPDATE_SKILLS = "UPDATE postings SET skills = %s WHERE id = %s"


def renormalize(conn) -> int:
    """Normalize every posting's skills again; return how many postings changed."""
    changed = 0
    for posting_id, skills in conn.execute(SELECT_SKILLS).fetchall():
        cleaned = normalize_skills(skills)
        if cleaned != skills:
            conn.execute(UPDATE_SKILLS, (cleaned, posting_id))
            changed += 1
    return changed


if __name__ == "__main__":
    with psycopg.connect(DATABASE_URL) as conn:
        print(f"Updated {renormalize(conn)} postings")