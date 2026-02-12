"""
Study material generation and export CLI commands.
"""

import json

from src.cli import get_db_session, resolve_class_id
from src.database import StudySet, StudyCard
from src.study_generator import generate_study_material, VALID_MATERIAL_TYPES
from src.study_export import (
    export_flashcards_tsv,
    export_flashcards_csv,
    export_study_pdf,
    export_study_docx,
)
from src.export_utils import sanitize_filename


def register_study_commands(subparsers):
    """Register study material subcommands."""

    # generate-study
    p = subparsers.add_parser("generate-study", help="Generate study materials.")
    p.add_argument("--class", dest="class_id", type=int, help="Class ID.")
    p.add_argument(
        "--type", dest="material_type", required=True,
        choices=list(VALID_MATERIAL_TYPES),
        help="Type of study material.",
    )
    p.add_argument("--quiz", dest="quiz_id", type=int, help="Source quiz ID.")
    p.add_argument("--topic", type=str, help="Topic to generate about.")
    p.add_argument("--title", type=str, help="Title for the study set.")

    # export-study
    p = subparsers.add_parser("export-study", help="Export a study set to file.")
    p.add_argument("study_set_id", type=int, help="Study set ID to export.")
    p.add_argument(
        "--format", dest="fmt", required=True,
        choices=["tsv", "csv", "pdf", "docx"],
        help="Export format.",
    )
    p.add_argument("--output", type=str, help="Output file path.")


def handle_generate_study(config, args):
    """Generate study materials using LLM."""
    engine, session = get_db_session(config)
    try:
        class_id = resolve_class_id(config, args, session)
        study_set = generate_study_material(
            session=session,
            class_id=class_id,
            material_type=args.material_type,
            config=config,
            quiz_id=args.quiz_id,
            topic=args.topic,
            title=args.title,
        )
        if study_set:
            card_count = (
                session.query(StudyCard)
                .filter_by(study_set_id=study_set.id)
                .count()
            )
            print(f"[OK] Generated study set: {study_set.title} (ID: {study_set.id})")
            print(f"   Type: {study_set.material_type}")
            print(f"   Cards: {card_count}")
        else:
            print("Error: Failed to generate study material.")
    finally:
        session.close()


def handle_export_study(config, args):
    """Export a study set to file."""
    engine, session = get_db_session(config)
    try:
        study_set = session.query(StudySet).filter_by(id=args.study_set_id).first()
        if not study_set:
            print(f"Error: Study set with ID {args.study_set_id} not found.")
            return

        cards = (
            session.query(StudyCard)
            .filter_by(study_set_id=study_set.id)
            .order_by(StudyCard.sort_order)
            .all()
        )

        base_name = sanitize_filename(study_set.title or "study", default="study")
        fmt = args.fmt

        if fmt == "tsv":
            content = export_flashcards_tsv(study_set, cards)
            out_path = args.output or f"{base_name}.tsv"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
        elif fmt == "csv":
            content = export_flashcards_csv(study_set, cards)
            out_path = args.output or f"{base_name}.csv"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
        elif fmt == "pdf":
            buf = export_study_pdf(study_set, cards)
            out_path = args.output or f"{base_name}.pdf"
            with open(out_path, "wb") as f:
                f.write(buf.read())
        elif fmt == "docx":
            buf = export_study_docx(study_set, cards)
            out_path = args.output or f"{base_name}.docx"
            with open(out_path, "wb") as f:
                f.write(buf.read())

        print(f"[OK] Exported study set to: {out_path}")
    finally:
        session.close()
