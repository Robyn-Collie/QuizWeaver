"""
Performance import, analytics, and reteach CLI commands.
"""

import json

from src.classroom import get_class
from src.cli import get_db_session, resolve_class_id
from src.performance_analytics import compute_gap_analysis, get_class_summary
from src.performance_import import import_csv_data
from src.reteach_generator import generate_reteach_suggestions


def register_analytics_commands(subparsers):
    """Register analytics-related subcommands."""

    # import-performance
    p = subparsers.add_parser("import-performance", help="Import performance data from CSV.")
    p.add_argument("--class", dest="class_id", type=int, help="Class ID.")
    p.add_argument("--file", dest="csv_file", required=True, help="Path to CSV file.")
    p.add_argument("--quiz", dest="quiz_id", type=int, help="Quiz ID to associate with.")

    # analytics
    p = subparsers.add_parser("analytics", help="Show performance analytics for a class.")
    p.add_argument("--class", dest="class_id", type=int, help="Class ID.")
    p.add_argument(
        "--format",
        dest="fmt",
        default="text",
        choices=["text", "json"],
        help="Output format.",
    )

    # reteach
    p = subparsers.add_parser("reteach", help="Generate reteach suggestions.")
    p.add_argument("--class", dest="class_id", type=int, help="Class ID.")
    p.add_argument("--max", dest="max_suggestions", type=int, default=5, help="Max suggestions.")


def handle_import_performance(config, args):
    """Import performance data from CSV file."""
    engine, session = get_db_session(config)
    try:
        class_id = resolve_class_id(config, args, session)
        class_obj = get_class(session, class_id)
        if not class_obj:
            print(f"Error: Class with ID {class_id} not found.")
            return

        try:
            with open(args.csv_file, encoding="utf-8") as f:
                csv_text = f.read()
        except FileNotFoundError:
            print(f"Error: File not found: {args.csv_file}")
            return

        count, errors = import_csv_data(
            session,
            class_id,
            csv_text,
            quiz_id=getattr(args, "quiz_id", None),
        )

        if errors:
            for err in errors:
                print(f"  [FAIL] {err}")

        print(f"[OK] Imported {count} records for class: {class_obj.name}")
    finally:
        session.close()


def handle_analytics(config, args):
    """Show performance analytics for a class."""
    engine, session = get_db_session(config)
    try:
        class_id = resolve_class_id(config, args, session)
        class_obj = get_class(session, class_id)
        if not class_obj:
            print(f"Error: Class with ID {class_id} not found.")
            return

        summary = get_class_summary(session, class_id)
        gaps = compute_gap_analysis(session, class_id)

        fmt = getattr(args, "fmt", "text")
        if fmt == "json":
            print(json.dumps({"summary": summary, "gaps": gaps}, indent=2, default=str))
            return

        # Text format
        print(f"\nAnalytics for: {class_obj.name}")
        print("-" * 50)
        print(f"  Topics assessed:  {summary['total_topics_assessed']}")
        print(f"  Overall average:  {summary['overall_avg_score']:.1%}")
        print(f"  Topics at risk:   {summary['topics_at_risk']}")
        print(f"  Topics on track:  {summary['topics_on_track']}")
        if summary["strongest_topic"]:
            print(f"  Strongest topic:  {summary['strongest_topic']}")
        if summary["weakest_topic"]:
            print(f"  Weakest topic:    {summary['weakest_topic']}")
        print(f"  Data points:      {summary['total_data_points']}")

        if gaps:
            print("\nGap Analysis (worst first):")
            print(f"  {'Topic':<30} {'Actual':>7} {'Expected':>8} {'Gap':>6} {'Severity':<12}")
            print(f"  {'---':<30} {'---':>7} {'---':>8} {'---':>6} {'---':<12}")
            for g in gaps[:10]:
                print(
                    f"  {g['topic'][:28]:<30} {g['actual_score']:>6.0%} "
                    f"{g['expected_score']:>7.0%} {g['gap']:>+5.0%} "
                    f"{g['gap_severity']:<12}"
                )
    finally:
        session.close()


def handle_reteach(config, args):
    """Generate reteach suggestions based on gap analysis."""
    engine, session = get_db_session(config)
    try:
        class_id = resolve_class_id(config, args, session)
        class_obj = get_class(session, class_id)
        if not class_obj:
            print(f"Error: Class with ID {class_id} not found.")
            return

        suggestions = generate_reteach_suggestions(
            session=session,
            class_id=class_id,
            config=config,
            max_suggestions=args.max_suggestions,
        )

        if suggestions is None:
            print("Error: Failed to generate reteach suggestions.")
            return

        if not suggestions:
            print("No reteach suggestions needed -- all topics are on track.")
            return

        print(f"\nRe-teach Suggestions for: {class_obj.name}")
        print("=" * 60)
        for i, s in enumerate(suggestions, 1):
            print(f"\n{i}. {s.get('topic', 'Unknown')} [{s.get('priority', 'medium')}]")
            if s.get("gap_severity"):
                print(f"   Severity: {s['gap_severity']}")
            if s.get("lesson_plan"):
                print(f"   Plan: {s['lesson_plan'][:80]}")
            activities = s.get("activities", [])
            if activities:
                print("   Activities:")
                for act in activities[:3]:
                    print(f"     - {act}")
    finally:
        session.close()
