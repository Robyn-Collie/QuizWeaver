"""
Quiz listing, viewing, export, and audio generation CLI commands.
"""

import json

from src.cli import get_db_session
from src.database import Question, Quiz
from src.export import export_csv, export_docx, export_gift, export_pdf, export_qti, export_quizizz_csv
from src.export_utils import sanitize_filename


def register_quiz_commands(subparsers):
    """Register quiz-related subcommands."""

    # list-quizzes
    p = subparsers.add_parser("list-quizzes", help="List all quizzes.")
    p.add_argument("--class", dest="class_id", type=int, help="Filter by class ID.")

    # view-quiz
    p = subparsers.add_parser("view-quiz", help="Display quiz content in terminal.")
    p.add_argument("quiz_id", type=int, help="Quiz ID to view.")
    p.add_argument("--show-answers", action="store_true", help="Show correct answers.")

    # export-quiz
    p = subparsers.add_parser("export-quiz", help="Export a quiz to file.")
    p.add_argument("quiz_id", type=int, help="Quiz ID to export.")
    p.add_argument(
        "--format",
        dest="fmt",
        required=True,
        choices=["csv", "docx", "gift", "pdf", "qti", "quizizz"],
        help="Export format.",
    )
    p.add_argument("--output", type=str, help="Output file path.")

    # generate-audio
    p = subparsers.add_parser("generate-audio", help="Generate TTS audio for a quiz.")
    p.add_argument("quiz_id", type=int, help="Quiz ID to generate audio for.")
    p.add_argument("--lang", default="en", help="Language code (default: en).")


def handle_list_quizzes(config, args):
    """List all quizzes with ID, title, class, date, question count."""
    engine, session = get_db_session(config)
    try:
        query = session.query(Quiz)
        class_filter = getattr(args, "class_id", None)
        if class_filter:
            query = query.filter(Quiz.class_id == int(class_filter))
        quizzes = query.order_by(Quiz.id).all()

        if not quizzes:
            print("No quizzes found.")
            return

        print(f"\n{'ID':>5}  {'Title':<40} {'Class':>5} {'Status':<12} {'Questions':>9}")
        print(f"{'---':>5}  {'---':<40} {'---':>5} {'---':<12} {'---':>9}")

        for q in quizzes:
            q_count = session.query(Question).filter_by(quiz_id=q.id).count()
            title = (q.title or "Untitled")[:38]
            status = (q.status or "")[:10]
            class_id = q.class_id or ""
            print(f"{q.id:>5}  {title:<40} {str(class_id):>5} {status:<12} {q_count:>9}")

        print(f"\nTotal: {len(quizzes)} quizzes")
    finally:
        session.close()


def handle_view_quiz(config, args):
    """Display quiz content in terminal."""
    engine, session = get_db_session(config)
    try:
        quiz = session.query(Quiz).filter_by(id=args.quiz_id).first()
        if not quiz:
            print(f"Error: Quiz with ID {args.quiz_id} not found.")
            return

        questions = session.query(Question).filter_by(quiz_id=quiz.id).order_by(Question.sort_order, Question.id).all()

        print(f"\n{quiz.title or 'Untitled Quiz'}")
        print(f"Status: {quiz.status or 'unknown'}  |  Questions: {len(questions)}")
        print("-" * 60)

        for i, q in enumerate(questions):
            data = q.data
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except (json.JSONDecodeError, ValueError):
                    data = {}
            if not isinstance(data, dict):
                data = {}

            q_type = q.question_type or data.get("type", "mc")
            text = q.text or data.get("text", "")
            print(f"\n{i + 1}. [{q_type.upper()}] ({q.points or 0} pts)")
            print(f"   {text}")

            options = data.get("options", [])
            if q_type in ("mc", "multiple_choice") and options:
                letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                for j, opt in enumerate(options):
                    ltr = letters[j] if j < len(letters) else str(j)
                    opt_text = opt.get("text", str(opt)) if isinstance(opt, dict) else str(opt)
                    print(f"     {ltr}. {opt_text}")

            if args.show_answers:
                answer = data.get("correct_answer") or data.get("answer", "")
                if not answer:
                    idx = data.get("correct_index")
                    if idx is not None and options:
                        try:
                            opt = options[int(idx)]
                            answer = opt.get("text", str(opt)) if isinstance(opt, dict) else str(opt)
                        except (IndexError, ValueError):
                            pass
                if answer:
                    print(f"     >> Answer: {answer}")
    finally:
        session.close()


def handle_export_quiz(config, args):
    """Export a quiz to file."""
    engine, session = get_db_session(config)
    try:
        quiz = session.query(Quiz).filter_by(id=args.quiz_id).first()
        if not quiz:
            print(f"Error: Quiz with ID {args.quiz_id} not found.")
            return

        questions = session.query(Question).filter_by(quiz_id=quiz.id).order_by(Question.sort_order, Question.id).all()

        if not questions:
            print(f"Error: Quiz {args.quiz_id} has no questions.")
            return

        # Parse style profile
        style_profile = quiz.style_profile
        if isinstance(style_profile, str):
            try:
                style_profile = json.loads(style_profile)
            except (json.JSONDecodeError, ValueError):
                style_profile = {}
        if not isinstance(style_profile, dict):
            style_profile = {}

        base_name = sanitize_filename(quiz.title or "quiz", default="quiz")
        fmt = args.fmt

        if fmt == "csv":
            content = export_csv(quiz, questions, style_profile)
            out_path = args.output or f"{base_name}.csv"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
        elif fmt == "docx":
            buf = export_docx(quiz, questions, style_profile)
            out_path = args.output or f"{base_name}.docx"
            with open(out_path, "wb") as f:
                f.write(buf.read())
        elif fmt == "gift":
            content = export_gift(quiz, questions)
            out_path = args.output or f"{base_name}.gift.txt"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
        elif fmt == "pdf":
            buf = export_pdf(quiz, questions, style_profile)
            out_path = args.output or f"{base_name}.pdf"
            with open(out_path, "wb") as f:
                f.write(buf.read())
        elif fmt == "qti":
            buf = export_qti(quiz, questions)
            out_path = args.output or f"{base_name}.qti.zip"
            with open(out_path, "wb") as f:
                f.write(buf.read())
        elif fmt == "quizizz":
            content = export_quizizz_csv(quiz, questions, style_profile)
            out_path = args.output or f"{base_name}_quizizz.csv"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)

        print(f"[OK] Exported quiz to: {out_path}")
    finally:
        session.close()


def handle_generate_audio(config, args):
    """Generate TTS audio files for all questions in a quiz."""
    from src.tts_generator import generate_quiz_audio, get_quiz_audio_dir, is_tts_available

    if not is_tts_available():
        print("Error: gTTS is not installed. Run: pip install gtts")
        return

    engine, session = get_db_session(config)
    try:
        quiz = session.query(Quiz).filter_by(id=args.quiz_id).first()
        if not quiz:
            print(f"Error: Quiz with ID {args.quiz_id} not found.")
            return

        questions = session.query(Question).filter_by(quiz_id=quiz.id).order_by(Question.sort_order, Question.id).all()

        if not questions:
            print(f"Error: Quiz {args.quiz_id} has no questions.")
            return

        # Build question dicts for the generator
        question_dicts = []
        for q in questions:
            data = q.data
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except (json.JSONDecodeError, ValueError):
                    data = {}
            if not isinstance(data, dict):
                data = {}
            question_dicts.append({"id": q.id, "text": q.text or data.get("text", ""), "options": data.get("options", [])})

        audio_dir = get_quiz_audio_dir(args.quiz_id)
        lang = getattr(args, "lang", "en") or "en"

        results = generate_quiz_audio(question_dicts, audio_dir, lang=lang)
        print(f"[OK] Generated audio for {len(results)} questions in {audio_dir}/")
    finally:
        session.close()
