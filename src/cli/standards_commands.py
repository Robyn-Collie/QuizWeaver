"""
Standards browsing and reload CLI commands.
"""

from src.cli import get_db_session
from src.standards import (
    STANDARD_SETS,
    ensure_standard_set_loaded,
    get_standard_sets_in_db,
    list_standards,
    load_standard_set,
    search_standards,
)
from src.database import Standard


def register_standards_commands(subparsers):
    """Register standards subcommands."""

    p = subparsers.add_parser("browse-standards", help="Browse educational standards.")
    p.add_argument(
        "--set",
        dest="standard_set",
        choices=list(STANDARD_SETS.keys()),
        help="Standard set to browse.",
    )
    p.add_argument("--search", type=str, help="Search text.")
    p.add_argument("--subject", type=str, help="Filter by subject.")
    p.add_argument("--grade", dest="grade_band", type=str, help="Filter by grade band.")

    # --- Reload Standards Command ---
    r = subparsers.add_parser(
        "reload-standards",
        help="Reload standards from JSON data files into the database.",
    )
    r.add_argument(
        "--set",
        dest="standard_set",
        choices=list(STANDARD_SETS.keys()),
        help="Specific standard set to reload. If omitted, reloads all sets that have JSON files.",
    )
    r.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing curriculum content (Essential Knowledge, etc.) even if already set.",
    )


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


def handle_reload_standards(config, args):
    """Reload standards from JSON data files into the database."""
    import os

    from src.standards import get_data_dir

    engine, session = get_db_session(config)
    try:
        force = getattr(args, "force", False)
        if args.standard_set:
            sets_to_load = [args.standard_set]
        else:
            # Reload all sets that have JSON files on disk
            data_dir = get_data_dir()
            sets_to_load = [
                key
                for key, info in STANDARD_SETS.items()
                if os.path.exists(os.path.join(data_dir, info["file"]))
            ]

        if not sets_to_load:
            print("No standard set JSON files found in data/.")
            return

        total_loaded = 0
        for set_key in sets_to_load:
            label = STANDARD_SETS[set_key]["label"]
            # Count existing before reload
            before_count = session.query(Standard).filter_by(standard_set=set_key).count()

            count = load_standard_set(session, set_key, force_update=force)

            after_count = session.query(Standard).filter_by(standard_set=set_key).count()
            new_count = after_count - before_count
            updated_count = count - new_count

            parts = []
            if new_count > 0:
                parts.append(f"{new_count} new")
            if updated_count > 0:
                parts.append(f"{updated_count} updated")
            detail = f" ({', '.join(parts)})" if parts else ""

            print(f"   {label}: loaded {count} standards{detail}")
            total_loaded += count

        if total_loaded == 0:
            print("[OK] All standards already up to date.")
        else:
            force_note = " (force overwrite)" if force else ""
            print(f"[OK] Loaded {total_loaded} standards across {len(sets_to_load)} set(s){force_note}.")
    finally:
        session.close()
