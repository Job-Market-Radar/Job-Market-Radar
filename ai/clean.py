import glob
import json
import os
from datetime import date

from bs4 import BeautifulSoup


def strip_html(text: str | None) -> str | None:
    """Turn HTML into plain text with single spaces."""
    if not text:
        return None
    plain = BeautifulSoup(text, "html.parser").get_text(" ")
    return " ".join(plain.split())


def clean_remotive(job: dict) -> dict:
    """Turn one raw Remotive job into the shared posting shape."""
    description = strip_html(job["description"]) or ""
    if job["salary"]:
        description = f"{description}\nSalary: {job['salary']}"

    return {
        "id": f"remotive:{job['id']}",
        "source": "remotive",
        "url": job["url"],
        "title": job["title"].strip(),
        "company": job["company_name"].strip(),
        "location": job["candidate_required_location"] or None,
        "remote": "remote",  # ←
        "posted_at": job["publication_date"],
        "description": description,
        "skills": [],
        "seniority": None,
        "salary_min": None,
        "salary_max": None,
        "currency": None,
    }


def parse_hn_header(text: str) -> dict:
    """Best guess at company, title, location and remote from a HN post's first line."""
    first_line = strip_html(text.split("<p>")[0]) or ""
    parts = [part.strip() for part in first_line.split("|")]

    if len(parts) < 2:
        return {"company": None, "title": None, "location": None, "remote": None}

    location = parts[2] if len(parts) > 2 else None
    remote = "remote" in first_line.lower()

    return {
        "company": parts[0] or None,
        "title": parts[1] or None,
        "location": location or None,
        "remote": remote,
    }


def clean_hn(post: dict) -> dict:
    """Turn one raw Hacker News post into the shared posting shape."""
    header = parse_hn_header(post["text"])
    return {
        "id": f"hackernews:{post['id']}",
        "source": "hackernews",
        "url": f"https://news.ycombinator.com/item?id={post['id']}",
        "title": header["title"],
        "company": header["company"],
        "location": header["location"],
        "remote": "remote" if header["remote"] else "unknown",  # ←
        "posted_at": post["created_at"],
        "description": strip_html(post["text"]),
        "skills": [],
        "seniority": None,
        "salary_min": None,
        "salary_max": None,
        "currency": None,
    }


def latest_raw_file(source: str) -> str:
    """Return the newest raw file for a source, e.g. data/raw/remotive_2026-11-17.json."""
    files = sorted(glob.glob(os.path.join("data", "raw", f"{source}_*.json")))
    if not files:
        raise FileNotFoundError(f"No raw files for {source}. Run the fetcher first.")
    return files[-1]


def load_json(path: str) -> list[dict]:
    """Read a JSON file and return what's inside."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def remove_duplicates(postings: list[dict]) -> list[dict]:
    """Keep only the first posting for each company + title pair."""
    seen = set()
    unique = []
    for posting in postings:
        if posting["company"] and posting["title"]:
            key = (posting["company"].lower(), posting["title"].lower())
            if key in seen:
                continue
            seen.add(key)
        unique.append(posting)
    return unique


if __name__ == "__main__":
    remotive_raw = load_json(latest_raw_file("remotive"))
    hn_raw = load_json(latest_raw_file("hackernews"))

    postings = [clean_remotive(job) for job in remotive_raw] + [clean_hn(post) for post in hn_raw]
    before = len(postings)
    postings = remove_duplicates(postings)

    os.makedirs(os.path.join("data", "clean"), exist_ok=True)
    out_path = os.path.join("data", "clean", f"postings_{date.today().isoformat()}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(postings, f, ensure_ascii=False, indent=2)

    print(f"Cleaned {before} postings, removed {before - len(postings)} duplicates")
    print(f"Saved {len(postings)} postings to {out_path}")