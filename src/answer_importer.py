o"""
Imports golden answers from a two-column CSV into ground_truth.json.

Expected CSV format (what the user maintains):
  Blank or subject-header rows are skipped.
  Data rows: question_text (col 1), golden_answer (col 2)

Matching strategy: normalize both sides to ASCII + collapsed whitespace,
then find the longest common prefix >= MIN_MATCH_CHARS. This handles
encoding artifacts (e.g. Â, Ã, â) that appear in exported CSVs.
"""

import csv
import re
import unicodedata
from pathlib import Path

from .ground_truth import load, save
from .parser import KNOWN_SUBJECTS

MIN_MATCH_CHARS = 20


def _normalize(text: str) -> str:
    text = text.strip()
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\s+", " ", text)
    # Normalize spaces around punctuation so "assertion :" == "assertion:"
    text = re.sub(r"\s*([:.!?,])\s*", r"\1 ", text)
    return text.lower().strip()


def _parse_answers_csv(path: Path) -> list[tuple[str, str]]:
    """Return [(question_text, answer_text)] from the golden answers CSV."""
    pairs = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            if not any(cell.strip() for cell in row):
                continue
            col1 = row[0].strip() if len(row) > 0 else ""
            col2 = row[1].strip() if len(row) > 1 else ""
            if not col1:
                continue
            # Skip subject header rows
            if col1.lower() in KNOWN_SUBJECTS:
                continue
            # Skip the "Golden Answers" column-label row
            if col2.lower() == "golden answers":
                continue
            pairs.append((col1, col2))
    return pairs


def _best_match(q_norm: str, gt_data: dict) -> tuple[str | None, int]:
    """
    Return (best_question_id, score) from gt_data.
    Strategy 1: longest common prefix >= MIN_MATCH_CHARS.
    Strategy 2 (short queries < 30 chars): substring match inside any entry.
    Strategy 3: token overlap — fraction of query words present in entry.
    """
    best_id, best_score = None, 0

    for qid, entry in gt_data.items():
        if entry.get("status") == "removed":
            continue
        entry_norm = _normalize(entry.get("question", ""))

        # Strategy 1: common prefix length
        prefix_score = 0
        for a, b in zip(q_norm, entry_norm):
            if a == b:
                prefix_score += 1
            else:
                break
        if prefix_score > best_score:
            best_score, best_id = prefix_score, qid

    # Strategy 2: for short queries, check if query is a substring of any entry
    if (best_score < MIN_MATCH_CHARS) and len(q_norm) < 30:
        for qid, entry in gt_data.items():
            if entry.get("status") == "removed":
                continue
            entry_norm = _normalize(entry.get("question", ""))
            if q_norm in entry_norm:
                return qid, MIN_MATCH_CHARS  # treat as matched

    # Strategy 3: token overlap as tiebreaker / fallback
    if best_score < MIN_MATCH_CHARS:
        q_tokens = set(q_norm.split())
        for qid, entry in gt_data.items():
            if entry.get("status") == "removed":
                continue
            entry_norm = _normalize(entry.get("question", ""))
            e_tokens = set(entry_norm.split())
            if not q_tokens:
                continue
            overlap = len(q_tokens & e_tokens) / len(q_tokens)
            # Require >60% token overlap and at least 4 matching tokens
            if overlap > 0.6 and len(q_tokens & e_tokens) >= 4:
                score = int(overlap * 100)
                if score > best_score:
                    best_score, best_id = score, qid

    return best_id, best_score


def import_answers(answers_csv: Path, gt_path: Path) -> dict:
    """
    Merge golden answers from answers_csv into ground_truth.json at gt_path.
    Only overwrites entries that currently have an empty answer.
    Returns a summary dict: {matched, skipped_empty_answer, unmatched, already_filled}.
    """
    pairs = _parse_answers_csv(answers_csv)
    gt_data = load(gt_path)

    matched = []
    skipped_empty = []
    unmatched = []
    already_filled = []

    for raw_q, raw_a in pairs:
        q_norm = _normalize(raw_q)
        qid, score = _best_match(q_norm, gt_data)

        if qid is None or score < MIN_MATCH_CHARS:
            unmatched.append(raw_q[:80])
            continue

        entry = gt_data[qid]
        if entry.get("answer", "").strip():
            already_filled.append(entry["question"][:60])
            continue

        if not raw_a:
            skipped_empty.append(entry["question"][:60])
            continue

        entry["answer"] = raw_a
        entry["status"] = "filled"
        matched.append(entry["question"][:60])

    save(gt_data, gt_path)

    return {
        "matched": matched,
        "skipped_empty_answer": skipped_empty,
        "unmatched": unmatched,
        "already_filled": already_filled,
    }


def print_import_summary(summary: dict) -> None:
    print(f"\n  Filled in:        {len(summary['matched'])}")
    for q in summary["matched"]:
        print(f"    ✓ {q}")

    if summary["already_filled"]:
        print(f"\n  Already had answer (kept): {len(summary['already_filled'])}")

    if summary["skipped_empty_answer"]:
        print(f"\n  Matched but no answer provided ({len(summary['skipped_empty_answer'])} — still needs_fill):")
        for q in summary["skipped_empty_answer"]:
            print(f"    - {q}")

    if summary["unmatched"]:
        print(f"\n  Could not match to any question ({len(summary['unmatched'])}):")
        for q in summary["unmatched"]:
            print(f"    ? {q}")
