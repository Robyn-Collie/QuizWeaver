"""
Lesson plan generation and export CLI commands.
"""

from src.cli import get_db_session, resolve_class_id
from src.database import LessonPlan
from src.lesson_plan_generator import generate_lesson_plan
from src.lesson_plan_export import export_lesson_plan_pdf, export_lesson_plan_docx
from src.export_utils import sanitize_filename


def register_lesson_plan_commands(subparsers):
    """Register lesson plan subcommands."""

    # generate-lesson-plan
    p = subparsers.add_parser("generate-lesson-plan", help="Generate a lesson plan.")
    p.add_argument("--class", dest="class_id", type=int, help="Class ID.")
    p.add_argument("--topics", type=str, required=True, help="Comma-separated topics.")
    p.add_argument("--standards", type=str, help="Comma-separated standards.")
    p.add_argument("--duration", type=int, default=50, help="Duration in minutes (default 50).")

    # export-lesson-plan
    p = subparsers.add_parser("export-lesson-plan", help="Export a lesson plan to file.")
    p.add_argument("plan_id", type=int, help="Lesson plan ID to export.")
    p.add_argument(
        "--format", dest="fmt", required=True,
        choices=["pdf", "docx"],
        help="Export format.",
    )
    p.add_argument("--output", type=str, help="Output file path.")


def handle_generate_lesson_plan(config, args):
    """Generate a lesson plan using LLM."""
    engine, session = get_db_session(config)
    try:
        class_id = resolve_class_id(config, args, session)
        topics = [t.strip() for t in args.topics.split(",") if t.strip()]
        standards = None
        if args.standards:
            standards = [s.strip() for s in args.standards.split(",") if s.strip()]

        plan = generate_lesson_plan(
            session=session,
            class_id=class_id,
            config=config,
            topics=topics,
            standards=standards,
            duration_minutes=args.duration,
        )
        if plan:
            print(f"[OK] Generated lesson plan: {plan.title} (ID: {plan.id})")
            print(f"   Duration: {plan.duration_minutes} min")
            print(f"   Status: {plan.status}")
        else:
            print("Error: Failed to generate lesson plan.")
    finally:
        session.close()


def handle_export_lesson_plan(config, args):
    """Export a lesson plan to file."""
    engine, session = get_db_session(config)
    try:
        plan = session.query(LessonPlan).filter_by(id=args.plan_id).first()
        if not plan:
            print(f"Error: Lesson plan with ID {args.plan_id} not found.")
            return

        base_name = sanitize_filename(plan.title or "lesson_plan", default="lesson_plan")
        fmt = args.fmt

        if fmt == "pdf":
            buf = export_lesson_plan_pdf(plan)
            out_path = args.output or f"{base_name}.pdf"
            with open(out_path, "wb") as f:
                f.write(buf.read())
        elif fmt == "docx":
            buf = export_lesson_plan_docx(plan)
            out_path = args.output or f"{base_name}.docx"
            with open(out_path, "wb") as f:
                f.write(buf.read())

        print(f"[OK] Exported lesson plan to: {out_path}")
    finally:
        session.close()
