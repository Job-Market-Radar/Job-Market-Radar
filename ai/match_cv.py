import os
import sys

import psycopg
from db import DATABASE_URL
from embed import MAX_CHARS, embed_texts, to_pgvector
from extract import MODEL as LLM_MODEL
from google import genai
from pypdf import PdfReader
from schema import CvSkills
from skills import normalize_skills

CANDIDATES = 50
TOP_N = 10
VECTOR_WEIGHT = 0.5
SKILL_WEIGHT = 0.5
# A job that lists only 1 or 2 skills shouldn't win just because you have them.
# For the ranking score, every job counts as having at least this many skills.
MIN_JOB_SKILLS = 3

# Only jobs with at least one skill: without skills we can't explain the match.
NEAREST_JOBS = """
SELECT p.id, p.title, p.company, p.skills, 1 - (e.embedding <=> %(cv)s::vector) AS vector_score
FROM posting_embeddings e
JOIN postings p ON p.id = e.posting_id
WHERE cardinality(p.skills) > 0
ORDER BY e.embedding <=> %(cv)s::vector
LIMIT %(limit)s
"""


def read_cv_text(path: str) -> str:
    """Get the plain text out of a PDF or .txt CV."""
    if path.lower().endswith(".pdf"):
        reader = PdfReader(path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    text = text.strip()
    if not text:
        raise ValueError("Could not read text from the CV")
    return text


def cv_skills(client, cv_text: str) -> list[str]:
    """Ask Gemini which technical skills the CV shows."""
    prompt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", "cv_skills_v1.txt")
    with open(prompt_path, encoding="utf-8") as f:
        prompt = f.read().replace("{cv}", cv_text[:MAX_CHARS])
    response = client.models.generate_content(
        model=LLM_MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": CvSkills},
    )
    return normalize_skills(CvSkills.model_validate_json(response.text).skills)


def score_job(
    cv_skill_set: set[str], job_skills: list[str], vector_score: float, stretched_vector: float
) -> dict:
    """Mix meaning and skill overlap into one score, and list matching/missing skills.

    vector_score is the real similarity (shown to the user).
    stretched_vector is the same thing rescaled to 0-1 among the candidates (used for ranking).
    """
    job_skill_set = set(normalize_skills(job_skills))
    matching = sorted(job_skill_set & cv_skill_set)
    missing = sorted(job_skill_set - cv_skill_set)
    # The honest share, as the contract defines it (shown to the user).
    overlap = len(matching) / len(job_skill_set) if job_skill_set else 0.0
    # The share used for ranking: short skill lists can't reach 100%.
    ranking_overlap = len(matching) / max(len(job_skill_set), MIN_JOB_SKILLS)
    score = VECTOR_WEIGHT * stretched_vector + SKILL_WEIGHT * ranking_overlap
    return {
        "score": score,
        "vector_score": vector_score,
        "skill_overlap": overlap,
        "matching_skills": matching,
        "missing_skills": missing,
    }


def match_cv(conn, client, cv_text: str, limit: int = TOP_N) -> tuple[list[str], list[dict]]:
    """Return the CV's skills and the best-matching jobs, best first."""
    skills = set(cv_skills(client, cv_text))
    cv_vector = embed_texts(client, [cv_text[:MAX_CHARS]], "RETRIEVAL_QUERY")[0]
    rows = conn.execute(NEAREST_JOBS, {"cv": to_pgvector(cv_vector), "limit": CANDIDATES}).fetchall()
    if not rows:
        return sorted(skills), []

    # Meaning scores are all squeezed together (e.g. 0.62-0.66), so stretch them:
    # the closest candidate becomes 1.0, the furthest 0.0.
    vector_scores = [row[4] for row in rows]
    lowest, highest = min(vector_scores), max(vector_scores)
    spread = highest - lowest

    results = []
    for posting_id, title, company, job_skills, vector_score in rows:
        stretched = (vector_score - lowest) / spread if spread > 0 else 1.0
        result = score_job(skills, job_skills, vector_score, stretched)
        result.update({"id": posting_id, "title": title, "company": company})
        results.append(result)

    results.sort(key=lambda r: r["score"], reverse=True)
    return sorted(skills), results[:limit]


if __name__ == "__main__":
    text = read_cv_text(sys.argv[1])
    client = genai.Client()
    with psycopg.connect(DATABASE_URL) as conn:
        skills, matches = match_cv(conn, client, text)

    print(f"CV skills: {', '.join(skills)}\n")
    for rank, m in enumerate(matches, start=1):
        job_skill_count = len(m["matching_skills"]) + len(m["missing_skills"])
        title = m["title"] or "(no title)"
        company = m["company"] or "(no company)"
        print(
            f"#{rank}  {m['score']:.2f}  (meaning {m['vector_score']:.3f}, "
            f"skills {m['skill_overlap']:.0%} of {job_skill_count})  {title} @ {company}"
        )
        print(f"     have:    {', '.join(m['matching_skills']) or '-'}")
        print(f"     missing: {', '.join(m['missing_skills']) or '-'}")