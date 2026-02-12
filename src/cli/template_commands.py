"""
Quiz template export/import CLI commands.
"""

import json

from src.cli import get_db_session, resolve_class_id
from src.export_utils import sanitize_filename
from src.template_manager import export_quiz_template, import_quiz_template, validate_template


def register_template_commands(subparsers):
    """Register template subcommands."""

    # export-template
    p = subparsers.add_parser("export-template", help="Export a quiz as a JSON template.")
    p.add_argument("quiz_id", type=int, help="Quiz ID to export as template.")
    p.add_argument("--output", type=str, help="Output file path.")

    # import-template
    p = subparsers.add_parser("import-template", help="Import a quiz from a JSON template.")
    p.add_argument("--file", dest="template_file", required=True, help="Path to template JSON file.")
    p.add_argument("--class", dest="class_id", type=int, help="Class ID to import into.")
    p.add_argument("--title", type=str, help="Override title for the imported quiz.")


def handle_export_template(config, args):
    """Export a quiz as a shareable JSON template."""
    engine, session = get_db_session(config)
    try:
        template = export_quiz_template(session, args.quiz_id)
        if not template:
            print(f"Error: Quiz with ID {args.quiz_id} not found.")
            return

        title = template.get("title", "quiz")
        base_name = sanitize_filename(title, default="template")
        out_path = args.output or f"{base_name}_template.json"

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(template, f, indent=2, default=str)

        print(f"[OK] Exported template to: {out_path}")
        print(f"   Questions: {template.get('question_count', 0)}")
    finally:
        session.close()


def handle_import_template(config, args):
    """Import a quiz from a JSON template file."""
    engine, session = get_db_session(config)
    try:
        try:
            with open(args.template_file, encoding="utf-8") as f:
                template_data = json.load(f)
        except FileNotFoundError:
            print(f"Error: File not found: {args.template_file}")
            return
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in template file: {e}")
            return

        # Validate
        is_valid, errors = validate_template(template_data)
        if not is_valid:
            print("Error: Template validation failed:")
            for err in errors:
                print(f"  [FAIL] {err}")
            return

        class_id = resolve_class_id(config, args, session)
        quiz = import_quiz_template(
            session=session,
            template_data=template_data,
            class_id=class_id,
            title=getattr(args, "title", None),
        )
        if quiz:
            print(f"[OK] Imported quiz: {quiz.title} (ID: {quiz.id})")
            print(f"   Class ID: {quiz.class_id}")
        else:
            print("Error: Failed to import template.")
    finally:
        session.close()
