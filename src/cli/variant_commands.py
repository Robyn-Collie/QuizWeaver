"""
Reading-level variant generation CLI commands.
"""

from src.cli import get_db_session
from src.database import Question
from src.variant_generator import READING_LEVELS, generate_variant


def register_variant_commands(subparsers):
    """Register variant subcommands."""

    p = subparsers.add_parser("generate-variant", help="Generate a reading-level variant of a quiz.")
    p.add_argument("quiz_id", type=int, help="Source quiz ID.")
    p.add_argument(
        "--level",
        dest="reading_level",
        required=True,
        choices=list(READING_LEVELS.keys()),
        help="Target reading level.",
    )
    p.add_argument("--title", type=str, help="Title for the variant quiz.")


def handle_generate_variant(config, args):
    """Generate a reading-level variant of a quiz."""
    engine, session = get_db_session(config)
    try:
        variant = generate_variant(
            session=session,
            quiz_id=args.quiz_id,
            reading_level=args.reading_level,
            config=config,
            title=getattr(args, "title", None),
        )
        if variant:
            q_count = session.query(Question).filter_by(quiz_id=variant.id).count()
            print(f"[OK] Generated variant: {variant.title} (ID: {variant.id})")
            print(f"   Reading level: {args.reading_level}")
            print(f"   Questions: {q_count}")
        else:
            print("Error: Failed to generate variant.")
    finally:
        session.close()
