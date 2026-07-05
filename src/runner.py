"""
Orchestrator: queries models, caches responses, runs grading, produces report.

Cache: cache/responses/<model_name>/<question_id>.json
  Each file stores {"question_id", "response", "subject", "timestamp"}.
  Re-running reuses cache. Delete cache/ to force fresh queries.
"""

import json
import os
import time
from pathlib import Path
from typing import Any

from tqdm import tqdm

from .grader import grade_response
from .ground_truth import get as get_truth, check_completeness
from .parser import load_questions, print_question_summary
from .reporter import generate_report

CACHE_ROOT = Path(__file__).parent.parent / "cache" / "responses"


def _cache_path(model_name: str, question_id: str) -> Path:
    safe_name = model_name.replace(" ", "_").replace("(", "").replace(")", "").replace("/", "-")
    return CACHE_ROOT / safe_name / f"{question_id}.json"


def _load_cached(model_name: str, question_id: str) -> str | None:
    p = _cache_path(model_name, question_id)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f).get("response")
    return None


def _save_cached(model_name: str, question_id: str, subject: str, response: str) -> None:
    p = _cache_path(model_name, question_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({
            "question_id": question_id,
            "subject": subject,
            "response": response,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }, f, indent=2, ensure_ascii=False)


def _build_models(skip_models: list[str] | None = None) -> list:
    """Lazy-import and instantiate only models whose API keys are present."""
    from .models.openai_model import OpenAIModel
    from .models.claude_model import ClaudeModel
    from .models.gemini_model import GeminiModel
    from .models.grok_model import GrokModel

    skip = set(skip_models or [])
    candidates = [
        ("OPENAI_API_KEY", OpenAIModel),
        ("ANTHROPIC_API_KEY", ClaudeModel),
        ("GOOGLE_API_KEY", GeminiModel),
        ("XAI_API_KEY", GrokModel),
    ]
    models = []
    for env_key, ModelClass in candidates:
        if env_key not in os.environ:
            print(f"  [skip] {ModelClass.__name__}: {env_key} not set")
            continue
        instance = ModelClass()
        if instance.name in skip:
            print(f"  [skip] {instance.name}: in skip list")
            continue
        models.append(instance)
        print(f"  [ok]   {instance.name}")
    return models


def run_models(
    csv_path: str | Path,
    skip_models: list[str] | None = None,
    force_refresh: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """
    Query all available models for every question in the CSV.
    Returns { model_name: [ {question_id, subject, question, response} ] }
    """
    questions = load_questions(csv_path)
    print_question_summary(questions)

    print("Initialising models...")
    models = _build_models(skip_models)
    if not models:
        raise RuntimeError("No models available. Check your .env API keys.")

    results: dict[str, list[dict]] = {m.name: [] for m in models}

    for model in models:
        print(f"\nQuerying {model.name} ...")
        for q in tqdm(questions, desc=model.name, unit="q"):
            cached = None if force_refresh else _load_cached(model.name, q["id"])
            if cached is not None:
                response = cached
            else:
                try:
                    response = model.query(q["question"], q["subject"])
                except Exception as exc:
                    response = f"[ERROR: {exc}]"
                # Don't cache errors — next run will retry them
                if not response.startswith("[ERROR:"):
                    _save_cached(model.name, q["id"], q["subject"], response)

            results[model.name].append({
                "question_id": q["id"],
                "subject": q["subject"],
                "question": q["question"],
                "response": response,
            })

    return results


def _build_gemini_judge() -> object | None:
    """Return a Gemini GenerativeModel for judging, or None if key not set."""
    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        print("  [warn] GOOGLE_API_KEY not set — Gemini judge unavailable. Long answers will use keyword fallback.")
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        model_name = os.environ.get("GEMINI_JUDGE_MODEL", "gemini-2.5-pro")
        print(f"  [ok]   Gemini judge: {model_name}")
        return genai.GenerativeModel(model_name)
    except Exception as exc:
        print(f"  [warn] Could not initialise Gemini judge: {exc}")
        return None


def grade_all(
    model_results: dict[str, list[dict]],
    gt_path: Path | None = None,
) -> dict[str, list[dict]]:
    """
    Grade every (model, question) pair.
    Objective answers are graded by code; long/explanatory answers use Gemini.
    Returns same structure as model_results but with grading fields added.
    """
    filled, total = check_completeness(gt_path) if gt_path else (0, 0)
    if filled < total:
        print(f"\nWarning: {total - filled}/{total} ground truths are empty — those questions will be Ungraded.")

    print("\nInitialising judge...")
    gemini_judge = _build_gemini_judge()

    graded: dict[str, list[dict]] = {}
    for model_name, rows in model_results.items():
        print(f"\nGrading {model_name} ...")
        graded[model_name] = []
        for row in tqdm(rows, desc=model_name, unit="q"):
            truth_entry = get_truth(row["question_id"], gt_path) if gt_path else None
            ground_truth = truth_entry["answer"] if truth_entry else ""
            question_type = truth_entry["question_type"] if truth_entry else "analytical"

            grade_result = grade_response(
                question=row["question"],
                ground_truth=ground_truth,
                response=row["response"],
                question_type=question_type,
                gemini_model=gemini_judge,
            )
            graded[model_name].append({
                **row,
                "ground_truth": ground_truth,
                "classification": grade_result["classification"],
                "reasoning": grade_result["reasoning"],
                "key_point_coverage": grade_result.get("key_point_coverage"),
                "conciseness": grade_result.get("conciseness"),
            })

    return graded


def run_full_pipeline(
    csv_path: str | Path,
    gt_path: Path | None = None,
    skip_models: list[str] | None = None,
    force_refresh: bool = False,
    output_path: Path | None = None,
) -> Path:
    """End-to-end: query → grade → report. Returns path to the Excel report."""
    model_results = run_models(csv_path, skip_models=skip_models, force_refresh=force_refresh)
    graded = grade_all(model_results, gt_path=gt_path)
    kwargs = {"path": output_path} if output_path else {}
    report_path = generate_report(graded, **kwargs)
    print(f"\nReport saved: {report_path}")
    return report_path
