"""
Standards browsing CLI commands.
"""

from src.cli import get_db_session
from src.standards import (
    STANDARD_SETS,
    list_standards,
    search_standards,
    ensure_standard_set_loaded,
    get_standard_sets_in_db,
)


def register_standards_commands(subparsers):
    """Register standards subcommands."""

    p = subparsers.add_parser("browse-standards", help="Browse educational standards.")
    p.add_argument(
        "--set", dest="standard_set",
        choices=list(STANDARD_SETS.keys()),
        help="Standard set to browse.",
    )
    p.add_argument("--search", type=str, help="Search text.")
    p.add_argument("--subject", type=str, help="Filter by subject.")
    p.add_argument("--grade", dest="grade_band", type=str, help="Filter by grade band.")


def handle_browse_standards(config, args):
    """Browse standards with optional filters."""
    engine, session = get_db_session(config)
    try:
        # Ensure the requested set is loaded
        if args.standard_set:
            loaded = ensure_standard_set_loaded(session, args.standard_set)
            if loaded > 0:
                print(f"   Loaded {loaded} standards from {args.standard_set}")

        # Search or list
        if args.search:
            results = search_standards(
                session,
                query_text=args.search,
                subject=args.subject,
                grade_band=args.grade_band,
                standard_set=args.standard_set,
            )
        else:
            results = list_standards(
                session,
                subject=args.subject,
                grade_band=args.grade_band,
                standard_set=args.standard_set,
            )

        if not results:
            # Show what's available
            sets_in_db = get_standard_sets_in_db(session)
            if sets_in_db:
                print("No standards matching filters. Available sets:")
                for s in sets_in_db:
                    print(f"  {s['key']}: {s['label']} ({s['count']} standards)")
            else:
                print("No standards loaded. Use --set to load a standard set.")
                print(f"Available sets: {', '.join(STANDARD_SETS.keys())}")
            return

        print(f"\n{'Code':<15} {'Subject':<15} {'Grade':<8} {'Description'}")
        print(f"{'---':<15} {'---':<15} {'---':<8} {'---'}")

        for std in results[:50]:
            code = (std.code or "")[:13]
            subject = (std.subject or "")[:13]
            grade = (std.grade_band or "")[:6]
            desc = (std.description or "")[:60]
            print(f"{code:<15} {subject:<15} {grade:<8} {desc}")

        if len(results) > 50:
            print(f"\n... and {len(results) - 50} more. Use --search to narrow results.")
        print(f"\nTotal: {len(results)} standards")
    finally:
        session.close()
