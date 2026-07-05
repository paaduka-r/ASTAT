"""
ASTAT Benchmark CLI

Usage:
  python main.py --generate-template          # Step 1: scaffold ground_truth.json from CSV
  python main.py --run                        # Step 2: query all models (uses cache)
  python main.py --grade                      # Step 3: grade cached responses
  python main.py --report                     # Step 4: generate Excel report from graded JSON
  python main.py --all                        # Run steps 2–4 end-to-end
  python main.py --summary                    # Print question count by subject

Options:
  --csv PATH         Path to questions CSV  (default: data/questions.csv)
  --gt PATH          Path to ground_truth.json  (default: data/ground_truth.json)
  --out PATH         Path for Excel output  (default: output/results.xlsx)
  --skip MODEL,...   Comma-separated model names to skip
  --force-refresh    Ignore cache and re-query all models
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
DEFAULT_CSV = ROOT / "data" / "questions.csv"
DEFAULT_GT = ROOT / "data" / "ground_truth.json"
DEFAULT_OUT = ROOT / "output" / "results.xlsx"
GRADED_CACHE = ROOT / "cache" / "graded_results.json"


def cmd_summary(args):
    from src.parser import load_questions, print_question_summary
    questions = load_questions(args.csv)
    print_question_summary(questions)


def cmd_import_answers(args):
    from src.answer_importer import import_answers, print_import_summary
    from src.ground_truth import check_completeness

    summary = import_answers(args.answers_csv, args.gt)
    print_import_summary(summary)
    filled, total = check_completeness(args.gt)
    print(f"\nGround truth status: {filled}/{total} questions filled.")


def cmd_generate_template(args):
    from src.parser import load_questions
    from src.ground_truth import generate_template, check_completeness

    questions = load_questions(args.csv)
    generate_template(questions, path=args.gt)
    filled, total = check_completeness(args.gt)
    print(f"Template written to: {args.gt}")
    print(f"Status: {filled}/{total} questions have ground truths filled in.")
    if filled < total:
        print(f"  → Open {args.gt} and fill in the 'answer' field for each 'needs_fill' entry.")


def cmd_run(args):
    from src.runner import run_models

    skip = [s.strip() for s in args.skip.split(",")] if args.skip else None
    results = run_models(args.csv, skip_models=skip, force_refresh=args.force_refresh)

    GRADED_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(GRADED_CACHE, "w", encoding="utf-8") as f:
        json.dump({"stage": "responses", "data": results}, f, indent=2, ensure_ascii=False)
    print(f"\nResponses cached to: {GRADED_CACHE}")


def cmd_grade(args):
    from src.runner import grade_all

    if not GRADED_CACHE.exists():
        sys.exit("No cached responses found. Run --run first.")

    with open(GRADED_CACHE, encoding="utf-8") as f:
        cache = json.load(f)

    if cache.get("stage") == "graded":
        print("Responses already graded. Re-grading...")

    model_results = cache["data"]
    graded = grade_all(model_results, gt_path=args.gt)

    with open(GRADED_CACHE, "w", encoding="utf-8") as f:
        json.dump({"stage": "graded", "data": graded}, f, indent=2, ensure_ascii=False)
    print(f"\nGraded results saved to: {GRADED_CACHE}")


def cmd_report(args):
    from src.reporter import generate_report

    if not GRADED_CACHE.exists():
        sys.exit("No graded results found. Run --grade first.")

    with open(GRADED_CACHE, encoding="utf-8") as f:
        cache = json.load(f)

    if cache.get("stage") != "graded":
        sys.exit("Cache contains ungraded responses. Run --grade first.")

    path = generate_report(cache["data"], path=args.out)
    print(f"Report saved: {path}")


def cmd_report_html(args):
    from src.html_reporter import generate_html_report

    if not GRADED_CACHE.exists():
        sys.exit("No graded results found. Run --grade first.")

    with open(GRADED_CACHE, encoding="utf-8") as f:
        cache = json.load(f)

    if cache.get("stage") != "graded":
        sys.exit("Cache contains ungraded responses. Run --grade first.")

    html_path = args.out.with_suffix(".html")
    path = generate_html_report(cache["data"], path=html_path)
    print(f"HTML report saved: {path}")
    print(f"Open in browser: file://{path.resolve()}")


def cmd_report_csv(args):
    from src.reporter import generate_csv_report

    if not GRADED_CACHE.exists():
        sys.exit("No graded results found. Run --grade first.")

    with open(GRADED_CACHE, encoding="utf-8") as f:
        cache = json.load(f)

    if cache.get("stage") != "graded":
        sys.exit("Cache contains ungraded responses. Run --grade first.")

    paths = generate_csv_report(cache["data"], out_dir=args.out.parent)
    for p in paths:
        print(f"CSV saved: {p}")


def cmd_all(args):
    from src.runner import run_full_pipeline

    skip = [s.strip() for s in args.skip.split(",")] if args.skip else None
    run_full_pipeline(
        csv_path=args.csv,
        gt_path=args.gt,
        skip_models=skip,
        force_refresh=args.force_refresh,
        output_path=args.out,
    )


def main():
    parser = argparse.ArgumentParser(
        description="ASTAT: Are you Smarter than a 12th Grader? — Benchmark runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, metavar="PATH")
    parser.add_argument("--gt", type=Path, default=DEFAULT_GT, metavar="PATH")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, metavar="PATH")
    parser.add_argument("--skip", type=str, default="", metavar="MODEL,...",
                        help="Comma-separated model names to skip")
    parser.add_argument("--force-refresh", action="store_true",
                        help="Ignore cache and re-query all models")

    parser.add_argument("--answers-csv", type=Path, default=ROOT / "data" / "golden_answers.csv",
                        metavar="PATH", help="Path to golden answers CSV for --import-answers")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--summary", action="store_true",
                       help="Print question count by subject")
    group.add_argument("--import-answers", action="store_true",
                       help="Merge golden answers CSV into ground_truth.json")
    group.add_argument("--generate-template", action="store_true",
                       help="Scaffold data/ground_truth.json from CSV")
    group.add_argument("--run", action="store_true",
                       help="Query all models and cache responses")
    group.add_argument("--grade", action="store_true",
                       help="Grade cached responses against ground truths")
    group.add_argument("--report", action="store_true",
                       help="Generate Excel report from graded results")
    group.add_argument("--report-csv", action="store_true",
                       help="Generate CSV files importable into Google Sheets")
    group.add_argument("--report-html", action="store_true",
                       help="Generate a self-contained HTML report viewable in any browser")
    group.add_argument("--all", action="store_true",
                       help="Run query → grade → report end-to-end")

    args = parser.parse_args()

    if args.summary:
        cmd_summary(args)
    elif args.import_answers:
        cmd_import_answers(args)
    elif args.generate_template:
        cmd_generate_template(args)
    elif args.run:
        cmd_run(args)
    elif args.grade:
        cmd_grade(args)
    elif args.report:
        cmd_report(args)
    elif args.report_csv:
        cmd_report_csv(args)
    elif args.report_html:
        cmd_report_html(args)
    elif args.all:
        cmd_all(args)


if __name__ == "__main__":
    main()
