import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from costs import cost_usd
from skills import normalize_skills

FIELDS = ["seniority", "remote", "salary_min", "salary_max", "currency", "salary_period"]


def read_jsonl(path: str) -> list[dict]:
    """Read a JSONL file: one JSON object per line."""
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def field_accuracy(labels: dict, predictions: dict, field: str) -> float:
    """Share of postings where the AI's answer equals your label."""
    correct = 0
    for posting_id, label in labels.items():
        prediction = predictions.get(posting_id)
        if prediction is not None and prediction[field] == label[field]:
            correct += 1
    return correct / len(labels)


def skill_scores(labels: dict, predictions: dict) -> tuple[float, float]:
    """Precision and recall of the skills, over all postings together."""
    in_both = 0
    total_predicted = 0
    total_labeled = 0
    for posting_id, label in labels.items():
        prediction = predictions.get(posting_id)
        real = set(normalize_skills(label["skills"]))
        guessed = set(normalize_skills(prediction["skills"])) if prediction else set()
        in_both += len(real & guessed)
        total_predicted += len(guessed)
        total_labeled += len(real)
    precision = in_both / total_predicted if total_predicted else 0
    recall = in_both / total_labeled if total_labeled else 0
    return precision, recall


def speed_and_cost(predictions: dict, model: str) -> None:
    """Average time and tokens per posting, and what 1,000 postings would cost."""
    rows = [row for row in predictions.values() if "seconds" in row]
    if not rows:
        print("\n(no time/token data in this file)")
        return
    count = len(rows)
    seconds = sum(row["seconds"] for row in rows) / count
    input_tokens = sum(row["input_tokens"] for row in rows) / count
    output_tokens = sum(row["output_tokens"] for row in rows) / count
    per_1000 = cost_usd(model, input_tokens * 1000, output_tokens * 1000)
    print(f"\n{'avg time':15} {seconds:.1f} s per posting")
    print(f"{'avg tokens':15} {input_tokens:.0f} in, {output_tokens:.0f} out")
    print(f"{'cost':15} ${per_1000:.2f} per 1,000 postings (paid tier)")


def show_mistakes(labels: dict, predictions: dict) -> None:
    """Print every disagreement, so you can see WHY the AI was wrong."""
    for posting_id, label in labels.items():
        prediction = predictions.get(posting_id)
        if prediction is None:
            print(f"\n{posting_id}: SKIPPED")
            continue
        problems = []
        for field in FIELDS:
            if prediction[field] != label[field]:
                problems.append(f"  {field}: you={label[field]!r}  ai={prediction[field]!r}")
        real = set(normalize_skills(label["skills"]))
        guessed = set(normalize_skills(prediction["skills"]))
        if guessed - real:
            problems.append(f"  skills the AI ADDED:  {sorted(guessed - real)}")
        if real - guessed:
            problems.append(f"  skills the AI MISSED: {sorted(real - guessed)}")
        if problems:
            print(f"\n{posting_id}")
            print("\n".join(problems))


if __name__ == "__main__":
    # Usage: python ai\eval\run_eval.py v3 --model gemini-3.8-flash   (old files: run_eval.py v3)
    args = sys.argv[1:]
    model = args[args.index("--model") + 1] if "--model" in args else None
    version = args[0] if args and not args[0].startswith("--") else "v1"
    name = f"predictions_{version}_{model}.jsonl" if model else f"predictions_{version}.jsonl"

    labels = {row["id"]: row for row in read_jsonl(os.path.join("ai", "eval", "labels.jsonl"))}
    predictions = {row["id"]: row for row in read_jsonl(os.path.join("ai", "eval", name))}
    # Compare fairly: only score postings that BOTH models answered.
    if "--same-as" in args:
        other = args[args.index("--same-as") + 1]
        other_path = os.path.join("ai", "eval", f"predictions_{version}_{other}.jsonl")
        other_ids = {row["id"] for row in read_jsonl(other_path)}
        labels = {pid: label for pid, label in labels.items() if pid in predictions and pid in other_ids}
    print(f"Prompt {version}, model {model or '(old run)'}: {len(predictions)} of {len(labels)} answered\n")
    for field in FIELDS:
        print(f"{field:15} {field_accuracy(labels, predictions, field):.0%}")
    precision, recall = skill_scores(labels, predictions)
    print(f"{'skills':15} precision {precision:.0%}, recall {recall:.0%}")

    if model:
        speed_and_cost(predictions, model)

    if "--mistakes" in sys.argv:
        show_mistakes(labels, predictions)