"""
Class management CLI commands (edit, delete, delete-lesson).
"""

from src.cli import get_db_session
from src.classroom import get_class, update_class, delete_class
from src.lesson_tracker import delete_lesson


def register_class_commands(subparsers):
    """Register class management subcommands."""

    # edit-class
    p = subparsers.add_parser("edit-class", help="Edit an existing class.")
    p.add_argument("class_id", type=int, help="Class ID to edit.")
    p.add_argument("--name", type=str, help="New name.")
    p.add_argument("--grade", type=str, help="New grade level.")
    p.add_argument("--subject", type=str, help="New subject.")

    # delete-class
    p = subparsers.add_parser("delete-class", help="Delete a class.")
    p.add_argument("class_id", type=int, help="Class ID to delete.")
    p.add_argument("--confirm", action="store_true", help="Skip confirmation prompt.")

    # delete-lesson
    p = subparsers.add_parser("delete-lesson", help="Delete a lesson log entry.")
    p.add_argument("lesson_id", type=int, help="Lesson ID to delete.")
    p.add_argument("--confirm", action="store_true", help="Skip confirmation prompt.")


def handle_edit_class(config, args):
    """Edit an existing class."""
    engine, session = get_db_session(config)
    try:
        updated = update_class(
            session,
            class_id=args.class_id,
            name=args.name,
            grade_level=args.grade,
            subject=args.subject,
        )
        if updated:
            print(f"[OK] Updated class: {updated.name} (ID: {updated.id})")
            if updated.grade_level:
                print(f"   Grade: {updated.grade_level}")
            if updated.subject:
                print(f"   Subject: {updated.subject}")
        else:
            print(f"Error: Class with ID {args.class_id} not found.")
    finally:
        session.close()


def handle_delete_class(config, args):
    """Delete a class (with confirmation)."""
    engine, session = get_db_session(config)
    try:
        class_obj = get_class(session, args.class_id)
        if not class_obj:
            print(f"Error: Class with ID {args.class_id} not found.")
            return

        if not args.confirm:
            try:
                print(f"Delete class '{class_obj.name}' (ID: {class_obj.id})? This cannot be undone.")
                print("Type 'yes' to confirm: ", end="")
                response = input().strip().lower()
                if response != "yes":
                    print("Cancelled.")
                    return
            except (EOFError, KeyboardInterrupt):
                print("\nCancelled.")
                return

        success = delete_class(session, args.class_id)
        if success:
            print(f"[OK] Deleted class: {class_obj.name} (ID: {class_obj.id})")
        else:
            print("Error: Failed to delete class.")
    finally:
        session.close()


def handle_delete_lesson(config, args):
    """Delete a lesson log entry (with confirmation)."""
    engine, session = get_db_session(config)
    try:
        if not args.confirm:
            try:
                print(f"Delete lesson log {args.lesson_id}? This cannot be undone.")
                print("Type 'yes' to confirm: ", end="")
                response = input().strip().lower()
                if response != "yes":
                    print("Cancelled.")
                    return
            except (EOFError, KeyboardInterrupt):
                print("\nCancelled.")
                return

        success = delete_lesson(session, args.lesson_id)
        if success:
            print(f"[OK] Deleted lesson log ID: {args.lesson_id}")
        else:
            print(f"Error: Lesson log with ID {args.lesson_id} not found.")
    finally:
        session.close()
