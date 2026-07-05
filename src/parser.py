"""
Parses the ASTAT questions CSV into a list of Question dicts.

Supports two CSV layouts automatically:
  1. Single-column alternating  — subject name row, then question rows, repeat
  2. Two-column with headers    — columns "Subject" and "Question" (or "subject"/"question")

The active layout is detected from the header row (or lack thereof).
Replacing the CSV file will just work as long as it follows either format.
"""

import csv
import hashlib
from pathlib import Path
from typing import Any

KNOWN_SUBJECTS = {
    "physics", "cs", "maths", "math", "mathematics",
    "chemistry", "english", "knowledge seeking",
    "video generation", "image generation",
    "music understanding", "summarisation", "summarization",
}


def _hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode()).hexdigest()[:16]


def _looks_like_subject(cell: str) -> bool:
    return cell.strip().lower() in KNOWN_SUBJECTS


def _load_raw_rows(path: Path) -> list[list[str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        return [row for row in reader if any(cell.strip() for cell in row)]


def _parse_two_column(rows: list[list[str]]) -> list[dict[str, Any]]:
    questions = []
    for i, row in enumerate(rows[1:], start=2):  # skip header
        if len(row) < 2:
            continue
        subject, question = row[0].strip(), row[1].strip()
        if not question:
            continue
        questions.append({
            "id": _hash(question),
            "subject": subject,
            "question": question,
            "row": i,
        })
    return questions


def _parse_single_column(rows: list[list[str]]) -> list[dict[str, Any]]:
    questions = []
    current_subject = "Unknown"
    row_num = 0
    for row in rows:
        row_num += 1
        cell = row[0].strip() if row else ""
        if not cell:
            continue
        if _looks_like_subject(cell):
            current_subject = cell
        else:
            questions.append({
                "id": _hash(cell),
                "subject": current_subject,
                "question": cell,
                "row": row_num,
            })
    return questions


def load_questions(csv_path: str | Path) -> list[dict[str, Any]]:
    """
    Load questions from the CSV file at csv_path.
    Returns a list of dicts: {id, subject, question, row}.
    Works regardless of whether questions are added, removed, or reordered.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Questions CSV not found: {path}")

    rows = _load_raw_rows(path)
    if not rows:
        return []

    header = [c.strip().lower() for c in rows[0]]
    if "subject" in header and ("question" in header or "questions" in header):
        return _parse_two_column(rows)

    # Default: single-column alternating format
    return _parse_single_column(rows)


def questions_by_subject(questions: list[dict]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for q in questions:
        result.setdefault(q["subject"], []).append(q)
    return result


def print_question_summary(questions: list[dict]) -> None:
    by_subject = questions_by_subject(questions)
    print(f"\n{'Subject':<25} {'Count':>5}")
    print("-" * 32)
    for subject, qs in by_subject.items():
        print(f"{subject:<25} {len(qs):>5}")
    print("-" * 32)
    print(f"{'TOTAL':<25} {len(questions):>5}\n")
