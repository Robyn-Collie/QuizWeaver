"""
Rubric generation and export CLI commands.
"""

from src.cli import get_db_session
from src.database import Rubric, RubricCriterion
from src.export_utils import sanitize_filename
from src.rubric_export import export_rubric_csv, export_rubric_docx, export_rubric_pdf
from src.rubric_generator import generate_rubric


def register_rubric_commands(subparsers):
    """Register rubric subcommands."""

    # generate-rubric
    p = subparsers.add_parser("generate-rubric", help="Generate a rubric for a quiz.")
    p.add_argument("quiz_id", type=int, help="Quiz ID to generate rubric for.")
    p.add_argument("--title", type=str, help="Title for the rubric.")

    # export-rubric
    p = subparsers.add_parser("export-rubric", help="Export a rubric to file.")
    p.add_argument("rubric_id", type=int, help="Rubric ID to export.")
    p.add_argument(
        "--format",
        dest="fmt",
        required=True,
        choices=["csv", "docx", "pdf"],
        help="Export format.",
    )
    p.add_argument("--output", type=str, help="Output file path.")


def handle_generate_rubric(config, args):
    """Generate a rubric for a quiz."""
    engine, session = get_db_session(config)
    try:
        rubric = generate_rubric(
            session=session,
            quiz_id=args.quiz_id,
            config=config,
            title=getattr(args, "title", None),
        )
        if rubric:
            criteria_count = session.query(RubricCriterion).filter_by(rubric_id=rubric.id).count()
            print(f"[OK] Generated rubric: {rubric.title} (ID: {rubric.id})")
            print(f"   Criteria: {criteria_count}")
        else:
            print("Error: Failed to generate rubric.")
    finally:
        session.close()


def handle_export_rubric(config, args):
    """Export a rubric to file."""
    engine, session = get_db_session(config)
    try:
        rubric = session.query(Rubric).filter_by(id=args.rubric_id).first()
        if not rubric:
            print(f"Error: Rubric with ID {args.rubric_id} not found.")
            return

        criteria = (
            session.query(RubricCriterion).filter_by(rubric_id=rubric.id).order_by(RubricCriterion.sort_order).all()
        )

        base_name = sanitize_filename(rubric.title or "rubric", default="rubric")
        fmt = args.fmt

        if fmt == "csv":
            content = export_rubric_csv(rubric, criteria)
            out_path = args.output or f"{base_name}.csv"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
        elif fmt == "docx":
            buf = export_rubric_docx(rubric, criteria)
            out_path = args.output or f"{base_name}.docx"
            with open(out_path, "wb") as f:
                f.write(buf.read())
        elif fmt == "pdf":
            buf = export_rubric_pdf(rubric, criteria)
            out_path = args.output or f"{base_name}.pdf"
            with open(out_path, "wb") as f:
                f.write(buf.read())

        print(f"[OK] Exported rubric to: {out_path}")
    finally:
        session.close()
