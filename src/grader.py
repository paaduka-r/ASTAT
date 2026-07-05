"""
Hybrid grader for the ASTAT benchmark.

Strategy:
  1. Objective check first — pure code, no API:
       • Number extraction + tolerance comparison
       • Multiple-choice letter detection
       • Keyword/phrase coverage
       If objective check is conclusive → done.

  2. Gemini as explanation-quality judge — only when:
       • Ground truth is long (complex multi-part or essay answer)
       • AND objective check is inconclusive
     Gemini receives the golden answer and the model's response;
     it COMPARES, never generates the correct answer itself.

  3. Generation tasks → Pass if output produced, Refusal if declined.
  4. Summarisation → ROUGE-1 token overlap (code only).
"""

import os
import re
import json
from typing import Any

PASS_THRESHOLD = 0.75
LONG_GT_CHARS = 120        # ground truths longer than this go to Gemini
LONG_RESPONSE_CHARS = 200  # used to distinguish Silent Failure vs Hallucination

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "are", "was", "were", "be", "been", "by", "this",
    "that", "it", "its", "as", "if", "so", "do", "does", "did", "not",
    "no", "from", "also", "which", "how", "what", "when", "where", "who",
}

GEMINI_JUDGE_MODEL = "gemini-2.5-pro"

_REFUSAL_PHRASES = [
    "i cannot", "i can't", "i'm unable", "i am unable",
    "not able to", "i don't have the ability",
    "as an ai", "as a language model",
]


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s\.\-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _tokens(text: str) -> set[str]:
    return {w for w in _norm(text).split() if w not in STOPWORDS and len(w) > 1}


# ---------------------------------------------------------------------------
# Objective check helpers
# ---------------------------------------------------------------------------

def _extract_numbers(text: str) -> list[float]:
    """Pull all numbers (int or float) out of text."""
    return [float(m) for m in re.findall(r"-?\d+(?:\.\d+)?", text)]


def _numbers_match(gt: str, response: str, tol: float = 0.02) -> bool | None:
    """
    If ground truth contains exactly one number, check whether the response
    contains a number within tol (relative tolerance).
    Returns True/False if decidable, None otherwise.
    """
    gt_nums = _extract_numbers(gt)
    if len(gt_nums) != 1:
        return None
    target = gt_nums[0]
    resp_nums = _extract_numbers(response)
    if not resp_nums:
        return False
    # relative tolerance; absolute for near-zero
    def close(a, b):
        denom = max(abs(b), 1e-9)
        return abs(a - b) / denom <= tol
    return any(close(n, target) for n in resp_nums)


def _multiple_choice_match(gt: str, response: str) -> bool | None:
    """
    If ground truth is / contains a choice letter (A/B/C/D or a/b/c/d),
    check whether the response selects that same letter.
    Returns True/False if decidable, None otherwise.
    """
    # Look for a leading option letter in ground truth
    m = re.match(r"^\s*([A-Da-d])\b", gt.strip())
    if not m:
        # also handle "a) and c)" style — extract all letters
        letters = re.findall(r"\b([A-Da-d])\)", gt)
        if not letters:
            return None
        resp_letters = set(re.findall(r"\b([A-Da-d])\b", response[:200]))
        return all(l.lower() in {r.lower() for r in resp_letters} for l in letters)
    letter = m.group(1).upper()
    # Check response selects that letter (look in first 300 chars)
    resp_letters = set(re.findall(r"\b([A-Da-d])\b", response[:300]))
    return letter in {r.upper() for r in resp_letters}


def _keyword_coverage(gt: str, response_norm: str) -> float:
    """Fraction of significant gt words found in response."""
    gt_words = [w for w in _norm(gt).split() if w not in STOPWORDS and len(w) > 2]
    if not gt_words:
        return 1.0
    hits = sum(1 for w in gt_words if w in response_norm)
    return hits / len(gt_words)


def _looks_like_refusal(response: str) -> bool:
    r = response.lower()
    return any(p in r for p in _REFUSAL_PHRASES)


# Phrases models use to identify themselves — stripped before sending to Gemini
_SELF_ID_PATTERNS = [
    r"as (an? )?(ai|llm|language model|chatgpt|gpt-?\d*|claude|gemini|grok|copilot)[,\s]",
    r"i('m| am) (chatgpt|gpt-?\d*|claude|gemini|grok|an ai|a language model)",
    r"(made|created|developed|built|trained) by (openai|anthropic|google|xai|deepmind|microsoft)",
    r"(openai|anthropic|google deepmind|xai)'s (model|ai|assistant|system)",
]
_SELF_ID_RE = re.compile("|".join(_SELF_ID_PATTERNS), re.IGNORECASE)


def _anonymise(response: str) -> str:
    """Strip model self-identification so the Gemini judge cannot detect the source."""
    return _SELF_ID_RE.sub("[REDACTED]", response)


# ---------------------------------------------------------------------------
# Summarisation (code-only, ROUGE-1)
# ---------------------------------------------------------------------------

def _score_summary(ground_truth: str, response: str) -> tuple[float, float]:
    ref = _tokens(ground_truth)
    hyp = _tokens(response)
    if not ref:
        return 0.0, 1.0
    coverage = len(ref & hyp) / len(ref)
    conciseness = min(1.0, (len(ref) / len(hyp)) * 2) if hyp else 0.0
    return round(coverage, 3), round(conciseness, 3)


# ---------------------------------------------------------------------------
# Objective grader (step 1)
# ---------------------------------------------------------------------------

def _objective_grade(ground_truth: str, response: str, question_type: str) -> dict | None:
    """
    Try to grade purely by code. Returns a result dict if conclusive, else None.

    For 'calculation' type: a correct number is NOT conclusive — working must
    still be checked by Gemini. We return None (defer) on a number match so
    Gemini can detect False Positives. We only return conclusively on a fail.

    For all other types: number match → Pass is fine (no working to verify).
    """
    gt = ground_truth.strip()
    resp_norm = _norm(response)
    is_calculation = question_type == "calculation"

    # --- Number comparison ---
    num_result = _numbers_match(gt, response)
    if num_result is not None:
        if num_result:
            if is_calculation:
                # Correct number found — but defer to Gemini to check the working
                return None
            return _make(
                "Pass",
                f"Correct numerical answer found in response (matched '{_extract_numbers(gt)[0]}').",
                None, None,
            )
        else:
            size = len(response.strip())
            cls = "Verifiable Hallucination" if size >= LONG_RESPONSE_CHARS else "Silent Failure"
            return _make(cls, f"Expected number {_extract_numbers(gt)[0]} not found in response.", None, None)

    # --- Multiple choice ---
    mc_result = _multiple_choice_match(gt, response)
    if mc_result is not None:
        if mc_result:
            return _make("Pass", "Correct answer choice identified in response.", None, None)
        else:
            size = len(response.strip())
            cls = "Verifiable Hallucination" if size >= LONG_RESPONSE_CHARS else "Silent Failure"
            return _make(cls, "Wrong answer choice selected.", None, None)

    # --- Short ground truth: keyword coverage ---
    if len(gt) <= LONG_GT_CHARS:
        cov = _keyword_coverage(gt, resp_norm)
        if cov >= PASS_THRESHOLD:
            if is_calculation:
                # Even with good keyword coverage, defer to Gemini for working check
                return None
            return _make(
                "Pass",
                f"Key terms matched ({cov:.0%} coverage).",
                round(cov, 3), None,
            )
        size = len(response.strip())
        cls = "Verifiable Hallucination" if size >= LONG_RESPONSE_CHARS else "Silent Failure"
        return _make(cls, f"Key terms coverage only {cov:.0%} (threshold {PASS_THRESHOLD:.0%}).", round(cov, 3), None)

    # Long ground truth → defer to Gemini
    return None


def _make(classification, reasoning, kpc, conc) -> dict:
    return {
        "classification": classification,
        "reasoning": reasoning,
        "key_point_coverage": kpc,
        "conciseness": conc,
    }


# ---------------------------------------------------------------------------
# Gemini judge (step 2 — only for long/explanatory answers)
# ---------------------------------------------------------------------------

def _gemini_grade(
    question: str,
    ground_truth: str,
    response: str,
    question_type: str,
    model,
) -> dict:
    """
    Use Gemini to compare the response against the golden answer.
    Gemini sees it as grading "Person A" — no model identity, no company names.
    Self-identifying phrases are stripped before sending.
    """
    anonymised_response = _anonymise(response)

    calculation_note = ""
    if question_type == "calculation":
        calculation_note = """
IMPORTANT — THIS IS A CALCULATION QUESTION:
Check the working/steps, not just the final answer.
If Person A states the correct final answer but the steps shown are wrong, use invalid
formulas, or the answer appears to be a lucky guess with no valid method, classify as
False Positive. A correct answer only counts as Pass if the reasoning that produced it
is also correct."""

    prompt = f"""You are an impartial exam grader evaluating a student's written answer.

Your only job is to compare Person A's answer against the golden answer and classify it.
Do not try to figure out who Person A is. Any identity cues have been removed — ignore them.
You are NOT generating or verifying the correct answer yourself; the golden answer is
provided by a human expert and is your sole reference.
{calculation_note}
QUESTION:
{question}

GOLDEN ANSWER:
{ground_truth}

PERSON A'S ANSWER:
{anonymised_response}

QUESTION TYPE: {question_type}

Classify Person A's answer as exactly one of:
- Pass: Matches the golden answer in substance; any explanation is consistent with it.
- False Positive: Correct final answer but explanation uses invalid or fabricated reasoning.
- Silent Failure: Wrong answer; too brief to identify where the logic broke down.
- Verifiable Hallucination: Wrong answer AND contains invented facts, fake rules, or fabricated citations.
- Refusal: Person A explicitly refused or claimed inability to answer.

Respond ONLY with this JSON — no text outside it:
{{
  "classification": "<one of the five above>",
  "reasoning": "<one sentence explaining your decision>",
  "key_point_coverage": <0.0–1.0 fraction of golden answer points present in Person A's answer, or null>,
  "conciseness": null
}}"""

    try:
        result = model.generate_content(
            prompt,
            generation_config={"temperature": 0.0, "candidate_count": 1},
        )
        raw = result.text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        valid = {"Pass", "False Positive", "Silent Failure", "Verifiable Hallucination", "Refusal"}
        if data.get("classification") not in valid:
            data["classification"] = "Silent Failure"
        return data
    except Exception as exc:
        return _make("Silent Failure", f"Gemini judge error: {exc}", None, None)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def grade_response(
    question: str,
    ground_truth: str,
    response: str,
    question_type: str,
    gemini_model=None,
    **_kwargs,
) -> dict[str, Any]:
    """
    Grade a single model response against ground truth.
    gemini_model: a google.generativeai.GenerativeModel instance, or None.
    """

    # API error during model querying — not a real response
    if response.startswith("[ERROR:"):
        return _make("Error", f"API error during model query: {response[8:80]}", None, None)

    # Modality-gate refusal
    if response.startswith("[REFUSAL:"):
        return _make("Refusal", "Model does not support this modality.", None, None)

    # No ground truth yet
    if not ground_truth.strip():
        return _make("Ungraded", "Ground truth not yet provided.", None, None)

    # Explicit refusal in response text
    if _looks_like_refusal(response) and len(response.strip()) < 300:
        return _make("Refusal", "Model declined to answer.", None, None)

    # Generation tasks
    if question_type == "generation":
        if _looks_like_refusal(response) or len(response.strip()) < 30:
            return _make("Refusal", "Model declined or produced negligible output.", None, None)
        return _make("Pass", "Model produced output (manual review recommended).", None, None)

    # Summarisation — code only
    if question_type == "summarisation":
        coverage, conciseness = _score_summary(ground_truth, response)
        threshold = 0.70
        cls = "Pass" if coverage >= threshold else "Silent Failure"
        return _make(
            cls,
            f"Token overlap coverage {coverage:.0%} ({'≥' if coverage >= threshold else '<'}{threshold:.0%} threshold). Conciseness {conciseness:.0%}.",
            coverage, conciseness,
        )

    # Step 1: try objective code-based grading
    result = _objective_grade(ground_truth, response, question_type)
    if result is not None:
        return result

    # Step 2: long/explanatory answer — use Gemini if available
    if gemini_model is not None:
        return _gemini_grade(question, ground_truth, response, question_type, gemini_model)

    # Fallback if Gemini unavailable: keyword coverage on long GT
    cov = _keyword_coverage(ground_truth, _norm(response))
    if cov >= PASS_THRESHOLD:
        return _make("Pass", f"Keyword coverage {cov:.0%} (no Gemini judge available).", round(cov, 3), None)
    size = len(response.strip())
    cls = "Verifiable Hallucination" if size >= LONG_RESPONSE_CHARS else "Silent Failure"
    return _make(cls, f"Keyword coverage only {cov:.0%} (no Gemini judge available).", round(cov, 3), None)
