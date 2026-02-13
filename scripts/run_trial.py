#!/usr/bin/env python
"""
Reusable trial run script for QuizWeaver.

Tests all CLI features with a specified LLM provider/model and generates exports.
Outputs go to trial_run_outputs/<model_name>/ for easy comparison.

Usage:
    python scripts/run_trial.py --provider gemini --model gemini-2.5-flash
    python scripts/run_trial.py --provider anthropic --model claude-haiku-4-5-20251001
    python scripts/run_trial.py --provider mock
    python scripts/run_trial.py --help
"""

import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
TRIAL_DB = ROOT / "trial_run.db"
CONFIG_PATH = ROOT / "config.yaml"
OUTPUT_BASE = ROOT / "trial_run_outputs"
SAMPLE_CSV_TEMPLATE = """student_id,topic,score,total,date
S001,cell structure,8,10,2026-02-10
S001,organelles,6,10,2026-02-10
S001,plant vs animal cells,9,10,2026-02-10
S001,cell membrane,5,10,2026-02-10
S001,photosynthesis,4,10,2026-02-10
S001,cellular respiration,3,10,2026-02-10
S002,cell structure,7,10,2026-02-10
S002,organelles,5,10,2026-02-10
S002,plant vs animal cells,8,10,2026-02-10
S002,cell membrane,4,10,2026-02-10
S002,photosynthesis,3,10,2026-02-10
S002,cellular respiration,2,10,2026-02-10
S003,cell structure,9,10,2026-02-10
S003,organelles,8,10,2026-02-10
S003,plant vs animal cells,7,10,2026-02-10
S003,cell membrane,6,10,2026-02-10
S003,photosynthesis,5,10,2026-02-10
S003,cellular respiration,4,10,2026-02-10
"""

# ---- Results tracking ----

results = []


def run(description, cmd_args, output_dir, expect_file=None):
    """Run a CLI command and track pass/fail."""
    full_cmd = [sys.executable, str(ROOT / "main.py")] + cmd_args
    t0 = time.time()
    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(ROOT),
        )
        elapsed = time.time() - t0
        ok = result.returncode == 0
        if expect_file and ok:
            ok = (output_dir / expect_file).exists()
        status = "[PASS]" if ok else "[FAIL]"
        print(f"  {status} {description} ({elapsed:.1f}s)")
        if not ok and result.stderr:
            for line in result.stderr.strip().split("\n")[:3]:
                print(f"        {line}")
        if not ok and result.stdout:
            # Show last few lines of stdout for debugging
            for line in result.stdout.strip().split("\n")[-3:]:
                print(f"        {line}")
        results.append({"description": description, "ok": ok, "time": elapsed})
        return ok, result.stdout
    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        print(f"  [FAIL] {description} (TIMEOUT {elapsed:.0f}s)")
        results.append({"description": description, "ok": False, "time": elapsed})
        return False, ""
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  [FAIL] {description} ({e})")
        results.append({"description": description, "ok": False, "time": elapsed})
        return False, ""


def extract_id(stdout, prefix="ID:"):
    """Extract an ID number from CLI output like '[OK] ... (ID: 3)'."""
    for line in stdout.split("\n"):
        if prefix in line:
            # Find the number after "ID:"
            idx = line.index(prefix) + len(prefix)
            num = ""
            for ch in line[idx:]:
                if ch.isdigit():
                    num += ch
                elif num:
                    break
            if num:
                return num
    return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="QuizWeaver trial run")
    parser.add_argument("--provider", default="gemini", help="LLM provider (default: gemini)")
    parser.add_argument("--model", default=None, help="Model name (e.g., gemini-2.5-flash)")
    parser.add_argument("--topics", default="cell structure,organelles,photosynthesis,cellular respiration,plant vs animal cells",
                        help="Comma-separated topics for quiz generation")
    parser.add_argument("--count", type=int, default=10, help="Number of quiz questions (default: 10)")
    parser.add_argument("--grade", default="7th Grade", help="Grade level (default: 7th Grade)")
    parser.add_argument("--clean", action="store_true", help="Clean previous trial data before running")
    args = parser.parse_args()

    # Load .env for API keys
    load_dotenv(ROOT / ".env")

    # Determine model name for folder naming
    model_label = args.model or args.provider
    output_dir = OUTPUT_BASE / model_label.replace("/", "_")

    print("=== QuizWeaver Trial Run ===")
    print(f"Provider: {args.provider}")
    print(f"Model: {args.model or '(provider default)'}")
    print(f"Output: {output_dir}")
    print(f"Topics: {args.topics}")
    print(f"Questions: {args.count}")
    print()

    # Check API key
    if args.provider == "gemini":
        if not os.getenv("GEMINI_API_KEY"):
            print("[ERROR] GEMINI_API_KEY not set in .env")
            sys.exit(1)
    elif args.provider == "anthropic":
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("[ERROR] ANTHROPIC_API_KEY not set in .env")
            sys.exit(1)

    # ---- Setup ----
    print("--- Setup ---")

    # Always start fresh — remove old trial DB
    if TRIAL_DB.exists():
        os.remove(TRIAL_DB)
        print("  [OK] Removed existing trial_run.db")

    # Clear cost log so rate limiter doesn't block new trial
    cost_log = ROOT / "api_costs.log"
    if cost_log.exists():
        os.remove(cost_log)
        print("  [OK] Cleared api_costs.log (reset rate limiter)")

    # Create output directory
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"  [OK] Created output dir: {output_dir.name}/")

    # Write sample performance CSV
    sample_csv = output_dir / "sample_performance.csv"
    sample_csv.write_text(SAMPLE_CSV_TEMPLATE.strip())
    print("  [OK] Wrote sample_performance.csv")

    # Back up and modify config
    with open(CONFIG_PATH) as f:
        original_config = f.read()

    trial_config = {
        "paths": {"database_file": str(TRIAL_DB)},
        "llm": {
            "provider": args.provider,
            "monthly_budget": 5.0,
            "max_calls_per_session": 200,
            "max_cost_per_session": 5.0,
        },
        "generation": {"default_grade_level": args.grade},
    }
    if args.model:
        trial_config["llm"]["model"] = args.model
    # Production mode to skip approval prompts
    if args.provider != "mock":
        trial_config["llm"]["mode"] = "production"

    with open(CONFIG_PATH, "w") as f:
        yaml.dump(trial_config, f)
    print(f"  [OK] Config set: provider={args.provider}, model={args.model or 'default'}")
    print()

    try:
        _run_trial(args, output_dir, model_label)
    finally:
        # Restore original config
        with open(CONFIG_PATH, "w") as f:
            f.write(original_config)
        print("\n  [OK] Config restored to original")


def _run_trial(args, output_dir, model_label):
    """Run the actual trial commands."""
    t_start = time.time()

    # ---- Class & Lesson Setup ----
    print("--- Class & Lesson Setup ---")
    ok, out = run("Create class", [
        "new-class", "--name", "7th Grade Life Science - Trial",
        "--grade", args.grade, "--subject", "Life Science"
    ], output_dir)
    class_id = extract_id(out) or "1"

    run("Log lesson", [
        "log-lesson", "--class", class_id,
        "--topics", args.topics,
        "--text", "Cell Biology Unit: cell structure, organelles, photosynthesis, cellular respiration",
        "--notes", "Covered cell structure, organelles, photosynthesis, cellular respiration"
    ], output_dir)
    print()

    # ---- Quiz Generation ----
    print("--- Quiz Generation ---")
    ok, out = run("Generate quiz from topics", [
        "generate-topics", "--class", class_id,
        "--topics", args.topics,
        "--count", str(args.count),
        "--title", f"Cell Biology Quiz ({model_label})"
    ], output_dir)
    quiz_id = extract_id(out) or "1"
    print()

    # ---- Quiz Exports (5 formats) ----
    print("--- Quiz Exports ---")
    for fmt in ["csv", "docx", "gift", "pdf", "qti"]:
        ext = "gift.txt" if fmt == "gift" else ("qti.zip" if fmt == "qti" else fmt)
        outfile = f"quiz.{ext}"
        run(f"Export quiz ({fmt})", [
            "export-quiz", quiz_id, "--format", fmt,
            "--output", str(output_dir / outfile)
        ], output_dir, expect_file=outfile)
    print()

    # ---- Study Materials (4 types x 4 formats = 16) ----
    print("--- Study Material Generation ---")
    study_ids = {}
    for stype in ["flashcard", "study_guide", "vocabulary", "review_sheet"]:
        ok, out = run(f"Generate {stype}", [
            "generate-study", "--type", stype,
            "--quiz", quiz_id,
            "--title", f"Cell Biology {stype.replace('_', ' ').title()}"
        ], output_dir)
        sid = extract_id(out)
        if sid:
            study_ids[stype] = sid
    print()

    print("--- Study Material Exports ---")
    for stype, sid in study_ids.items():
        for fmt in ["tsv", "csv", "pdf", "docx"]:
            outfile = f"{stype}.{fmt}"
            run(f"Export {stype} ({fmt})", [
                "export-study", sid, "--format", fmt,
                "--output", str(output_dir / outfile)
            ], output_dir, expect_file=outfile)
    print()

    # ---- Rubric ----
    print("--- Rubric Generation & Export ---")
    ok, out = run("Generate rubric", [
        "generate-rubric", quiz_id, "--title", "Cell Biology Rubric"
    ], output_dir)
    rubric_id = extract_id(out)
    if rubric_id:
        for fmt in ["csv", "docx", "pdf"]:
            outfile = f"rubric.{fmt}"
            run(f"Export rubric ({fmt})", [
                "export-rubric", rubric_id, "--format", fmt,
                "--output", str(output_dir / outfile)
            ], output_dir, expect_file=outfile)
    print()

    # ---- Variant ----
    print("--- Variant Generation & Export ---")
    ok, out = run("Generate ELL variant", [
        "generate-variant", quiz_id, "--level", "ell"
    ], output_dir)
    variant_id = extract_id(out)
    if variant_id:
        for fmt in ["csv", "docx", "gift", "pdf", "qti"]:
            ext = "gift.txt" if fmt == "gift" else ("qti.zip" if fmt == "qti" else fmt)
            outfile = f"variant_ell.{ext}"
            run(f"Export variant ({fmt})", [
                "export-quiz", variant_id, "--format", fmt,
                "--output", str(output_dir / outfile)
            ], output_dir, expect_file=outfile)
    print()

    # ---- Lesson Plan ----
    print("--- Lesson Plan Generation & Export ---")
    ok, out = run("Generate lesson plan", [
        "generate-lesson-plan",
        "--topics", args.topics,
        "--standards", "SOL LS.4",
        "--duration", "50"
    ], output_dir)
    plan_id = extract_id(out)
    if plan_id:
        for fmt in ["pdf", "docx"]:
            outfile = f"lesson_plan.{fmt}"
            run(f"Export lesson plan ({fmt})", [
                "export-lesson-plan", plan_id, "--format", fmt,
                "--output", str(output_dir / outfile)
            ], output_dir, expect_file=outfile)
    print()

    # ---- Template Export/Import ----
    print("--- Template Round-Trip ---")
    template_file = output_dir / "quiz_template.json"
    run("Export template", [
        "export-template", quiz_id,
        "--output", str(template_file)
    ], output_dir, expect_file="quiz_template.json")

    if template_file.exists():
        run("Import template (round-trip)", [
            "import-template",
            "--file", str(template_file),
            "--class", class_id,
            "--title", "Imported Template Quiz"
        ], output_dir)
    print()

    # ---- Performance & Analytics ----
    print("--- Performance & Analytics ---")
    sample_csv = output_dir / "sample_performance.csv"
    run("Import performance CSV", [
        "import-performance", "--file", str(sample_csv),
        "--class", class_id
    ], output_dir)

    run("Analytics", ["analytics", "--class", class_id], output_dir)

    run("Reteach suggestions", [
        "reteach", "--class", class_id, "--max", "5"
    ], output_dir)
    print()

    # ---- Info Commands ----
    print("--- Info Commands ---")
    run("Provider info", ["provider-info"], output_dir)
    run("Browse standards", ["browse-standards", "--set", "sol", "--search", "life"], output_dir)
    run("Cost summary", ["cost-summary"], output_dir)
    print()

    # ---- Summary ----
    elapsed = time.time() - t_start
    passed = sum(1 for r in results if r["ok"])
    failed = sum(1 for r in results if not r["ok"])
    total = len(results)

    # Count output files
    output_files = list(output_dir.glob("*"))
    output_files = [f for f in output_files if f.is_file() and f.name != "sample_performance.csv"]

    print("=" * 60)
    print(f"TRIAL RUN COMPLETE: {model_label}")
    print(f"  Commands: {passed}/{total} passed ({failed} failed)")
    print(f"  Output files: {len(output_files)} in {output_dir.name}/")
    print(f"  Total time: {elapsed:.0f}s")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    if failed:
        print("\nFailed commands:")
        for r in results:
            if not r["ok"]:
                print(f"  - {r['description']}")

    # Write summary file
    summary_path = output_dir / "SUMMARY.txt"
    with open(summary_path, "w") as f:
        f.write(f"QuizWeaver Trial Run - {model_label}\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Provider: {args.provider}\n")
        f.write(f"Model: {args.model or '(provider default)'}\n")
        f.write(f"Commands: {passed}/{total} passed\n")
        f.write(f"Output files: {len(output_files)}\n")
        f.write(f"Total time: {elapsed:.0f}s\n\n")
        f.write("Results:\n")
        for r in results:
            status = "PASS" if r["ok"] else "FAIL"
            f.write(f"  [{status}] {r['description']} ({r['time']:.1f}s)\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
