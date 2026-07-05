"""
Ground truth management.

Workflow:
  1. Run `python main.py --generate-template` to create data/ground_truth.json
     from the current CSV. Any questions without a ground truth get an empty
     "answer" field and a "status": "needs_fill" marker.
  2. Manually fill in the "answer" field for each question.
  3. When you replace the CSV with updated questions, re-run --generate-template.
     Existing filled-in answers are preserved; new questions get empty entries.
  4. Questions removed from the CSV are soft-deleted (marked "status": "removed")
     so you don't accidentally lose work.
"""

import json
from pathlib import Path
from typing import Any

GROUND_TRUTH_PATH = Path(__file__).parent.parent / "data" / "ground_truth.json"

QUESTION_TYPES = {
    "Physics": "calculation",
    "Chemistry": "calculation",
    "Maths": "calculation",
    "CS": "analytical",
    "English": "analytical",
    "Knowledge Seeking": "factual",
    "Music Understanding": "analytical",
    "Summarisation": "summarisation",
    "Summarization": "summarisation",
    "Video Generation": "generation",
    "Image Generation": "generation",
}


def _default_type(subject: str) -> str:
    return QUESTION_TYPES.get(subject, "analytical")


def load(path: Path = GROUND_TRUTH_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(data: dict[str, Any], path: Path = GROUND_TRUTH_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def generate_template(questions: list[dict], path: Path = GROUND_TRUTH_PATH) -> dict[str, Any]:
    """
    Merge current CSV questions into the ground truth JSON.
    - New questions get empty answer entries.
    - Existing filled answers are preserved exactly.
    - Questions no longer in the CSV are marked "removed".
    Returns the merged dict.
    """
    existing = load(path)
    current_ids = {q["id"] for q in questions}

    # Soft-delete questions that are no longer in the CSV
    for qid, entry in existing.items():
        if entry.get("status") != "removed" and qid not in current_ids:
            entry["status"] = "removed"

    # Add or update entries for current questions
    for q in questions:
        qid = q["id"]
        if qid in existing and existing[qid].get("status") != "removed":
            # Preserve existing answer; just refresh metadata
            existing[qid]["subject"] = q["subject"]
            existing[qid]["question"] = q["question"]
            if existing[qid].get("answer"):
                existing[qid]["status"] = "filled"
        else:
            existing[qid] = {
                "subject": q["subject"],
                "question": q["question"],
                "question_type": _default_type(q["subject"]),
                "answer": "",
                "notes": "",
                "status": "needs_fill",
            }

    save(existing, path)
    return existing


def check_completeness(path: Path = GROUND_TRUTH_PATH) -> tuple[int, int]:
    """Returns (filled_count, total_active_count)."""
    data = load(path)
    active = [v for v in data.values() if v.get("status") != "removed"]
    filled = [v for v in active if v.get("answer", "").strip()]
    return len(filled), len(active)


def get(question_id: str, path: Path = GROUND_TRUTH_PATH) -> dict[str, Any] | None:
    data = load(path)
    return data.get(question_id)
