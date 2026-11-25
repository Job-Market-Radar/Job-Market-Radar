import json
import os
import sys
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors
from pydantic import ValidationError
from schema import Extraction
from skills import normalize_skills

load_dotenv()

MODEL = "gemini-3.5-flash-lite"
SAMPLE = os.path.join("ai", "eval", "sample.jsonl")
SECONDS_BETWEEN_CALLS = 5


def read_jsonl(path: str) -> list[dict]:
    """Read a JSONL file: one JSON object per line."""
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build_prompt(template: str, posting: dict) -> str:
    """Put the posting's text into the prompt template."""
    text = posting["description"] or ""
    if posting["source"] == "remotive":
        text = f"Job title: {posting['title']}\n\n{text}"
    return template.replace("{posting}", text)


def new_usage() -> dict:
    """An empty counter for time and tokens."""
    return {"seconds": 0.0, "input_tokens": 0, "output_tokens": 0, "calls": 0}


def extract(client, prompt: str, model: str = MODEL, usage: dict | None = None) -> Extraction:
    """Ask the model once, and return its answer checked by pydantic.

    If a usage counter is given, add this call's time and tokens to it.
    """
    start = time.perf_counter()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": Extraction,
        },
    )
    if usage is not None:
        meta = response.usage_metadata
        usage["seconds"] += time.perf_counter() - start
        usage["input_tokens"] += meta.prompt_token_count or 0
        # "Thinking" is billed as output too, so count it.
        usage["output_tokens"] += (meta.candidates_token_count or 0) + (meta.thoughts_token_count or 0)
        usage["calls"] += 1
    # Counted before checking the shape: a wrongly shaped answer still costs money.
    return Extraction.model_validate_json(response.text)


def extract_with_retry(
    client, prompt: str, model: str = MODEL, usage: dict | None = None
) -> Extraction | None:
    """Try twice. If both fail, give up and return None."""
    for attempt in (1, 2):
        try:
            return extract(client, prompt, model, usage)
        except ValidationError as error:
            print(f"  attempt {attempt}: wrong shape ({error.error_count()} problems)")
        except errors.APIError as error:
            print(f"  attempt {attempt}: API error {error.code}, waiting 30s")
            time.sleep(30)
            continue
        time.sleep(SECONDS_BETWEEN_CALLS)
    return None


if __name__ == "__main__":
    # Usage: python ai\extract.py v3 --model gemini-3.8-flash
    args = sys.argv[1:]
    model = args[args.index("--model") + 1] if "--model" in args else MODEL
    version = args[0] if args and not args[0].startswith("--") else "v1"
    with open(os.path.join("ai", "prompts", f"extract_{version}.txt"), encoding="utf-8") as f:
        template = f.read()
    out_path = os.path.join("ai", "eval", f"predictions_{version}_{model}.jsonl")

    client = genai.Client()
    postings = read_jsonl(SAMPLE)
    saved = 0
    skipped = 0

    done = set()
    if os.path.exists(out_path):
        done = {row["id"] for row in read_jsonl(out_path)}
    todo = [p for p in postings if p["id"] not in done]
    print(f"Model {model}: {len(done)} already done, {len(todo)} to go")

    with open(out_path, "a", encoding="utf-8") as f:
        for number, posting in enumerate(todo, start=1):
            print(f"[{number}/{len(todo)}] {posting['id']}")
            usage = new_usage()
            result = extract_with_retry(client, build_prompt(template, posting), model, usage)
            if result is None:
                print("  skipped after 2 tries")
                skipped = skipped + 1
            else:
                row = {"id": posting["id"], **result.model_dump()}
                row["skills"] = normalize_skills(row["skills"])
                if posting["source"] == "remotive":
                    row["remote"] = "remote"
                row.update(usage)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                saved = saved + 1
            time.sleep(SECONDS_BETWEEN_CALLS)

    print(f"\nSaved {saved}, skipped {skipped} -> {out_path}")