"""
Topic-based generation CLI commands.
"""

from src.cli import get_db_session, resolve_class_id
from src.topic_generator import generate_from_topics


def register_topic_commands(subparsers):
    """Register topic generation subcommands."""

    p = subparsers.add_parser("generate-topics", help="Generate a quiz from topics (no source quiz needed).")
    p.add_argument("--class", dest="class_id", type=int, help="Class ID.")
    p.add_argument("--topics", type=str, required=True, help="Comma-separated topics.")
    p.add_argument("--count", type=int, default=10, help="Number of questions (default 10).")
    p.add_argument("--title", type=str, help="Title for the generated quiz.")


def handle_generate_topics(config, args):
    """Generate a quiz from topics without a source quiz."""
    engine, session = get_db_session(config)
    try:
        class_id = resolve_class_id(config, args, session)
        topics = [t.strip() for t in args.topics.split(",") if t.strip()]

        result = generate_from_topics(
            session=session,
            class_id=class_id,
            topics=topics,
            output_type="quiz",
            config=config,
            num_questions=args.count,
            title=args.title,
        )
        if result:
            print(f"[OK] Generated quiz: {result.title} (ID: {result.id})")
        else:
            print("Error: Failed to generate quiz from topics.")
    finally:
        session.close()
