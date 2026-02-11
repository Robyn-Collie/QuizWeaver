import os
import argparse
from dotenv import load_dotenv
import yaml
from datetime import datetime, date

# Import from our new library structure
from src.ingestion import ingest_content, get_retake_analysis
from src.agents import run_agentic_pipeline
from src.output import generate_pdf_preview, create_qti_package
from src.image_gen import generate_image
from src.database import get_engine, init_db, get_session, Lesson, Asset, Quiz, Question
from src.review import interactive_review
from src.classroom import create_class, get_class, list_classes, get_active_class, set_active_class
from src.lesson_tracker import log_lesson, list_lessons, get_assumed_knowledge
from src.cost_tracking import get_cost_summary, format_cost_report


def _get_db_session(config):
    """Helper to get a database engine and session."""
    engine = get_engine(config["paths"]["database_file"])
    init_db(engine)
    session = get_session(engine)
    return engine, session


def _resolve_class_id(config, args, session):
    """Resolve class_id from --class flag, config, or default to 1."""
    class_id = getattr(args, "class_id", None)
    if class_id is not None:
        return int(class_id)

    active = config.get("active_class_id")
    if active is not None:
        return int(active)

    # Default to legacy class
    return 1


def handle_ingest(config):
    """Handles the "ingest" command."""
    print("--- Starting Content Ingestion ---")
    engine = get_engine(config["paths"]["database_file"])
    init_db(engine)
    session = get_session(engine)
    ingest_content(session, config)
    session.close()
    print("[OK] Ingestion complete.")


def handle_generate(config, args):
    """Handles the "generate" command."""
    print("--- Starting Quiz Generation ---")
    engine, session = _get_db_session(config)

    # Resolve class context
    class_id = _resolve_class_id(config, args, session)
    class_obj = get_class(session, class_id)
    if class_obj:
        print(f"   Generating for class: {class_obj.name} (ID: {class_id})")
        if class_obj.grade_level:
            print(f"   Grade: {class_obj.grade_level}")

        # Show assumed knowledge summary
        knowledge = get_assumed_knowledge(session, class_id)
        if knowledge:
            topics = [f"{t} (depth:{d['depth']})" for t, d in knowledge.items()]
            print(f"   Assumed knowledge: {', '.join(topics[:5])}")
            if len(topics) > 5:
                print(f"   ... and {len(topics) - 5} more topics")

    # --- 1. Load Data & Analyze ---
    print("\nStep 1: Loading content and analyzing retake...")
    all_lessons = session.query(Lesson).all()
    content_summary = "\n".join([lesson.content for lesson in all_lessons])

    # Aggregate structured page data if available
    structured_data = []
    for lesson in all_lessons:
        if lesson.page_data:
            if isinstance(lesson.page_data, list):
                structured_data.extend(lesson.page_data)
            else:
                structured_data.append(lesson.page_data)

    all_assets = session.query(Asset).filter_by(asset_type="image").all()
    extracted_images = [asset.path for asset in all_assets]

    retake_text, est_q_count, img_count, img_ratio = get_retake_analysis(config)

    num_questions = args.count if args.count else est_q_count
    grade_level = (
        args.grade if args.grade else config["generation"]["default_grade_level"]
    )
    sol_standards = args.sol if args.sol else config["generation"]["sol_standards"]

    # --- 2. Create Quiz Record ---
    print("\nStep 2: Creating new quiz record...")
    style_profile = {
        "estimated_question_count": est_q_count,
        "image_ratio": img_ratio,
        "grade_level": grade_level,
        "sol_standards": sol_standards,
    }
    new_quiz = Quiz(
        title=config["generation"]["quiz_title"],
        class_id=class_id,
        status="generating",
        style_profile=style_profile,
    )
    session.add(new_quiz)
    session.commit()
    print(f"   - Created Quiz ID: {new_quiz.id}")

    print(f"   - Grade Level: {grade_level}")
    if sol_standards:
        sol_str = ", ".join(sol_standards)
        print(f"   - SOL Standards: {sol_str}")
    print(f"   - Targeting {num_questions} questions.")

    print("\nStep 3: Generating questions with AI Agent...")
    context = {
        "content_summary": content_summary,
        "structured_data": structured_data,
        "retake_text": retake_text,
        "num_questions": num_questions,
        "images": extracted_images[:],  # Copy to avoid mutation issues in loop
        "image_ratio": img_ratio,
        "grade_level": grade_level,
        "sol_standards": sol_standards,
    }

    questions = run_agentic_pipeline(config, context, class_id=class_id)

    if not questions:
        print("Error: AI Agent failed to generate valid questions.")
        new_quiz.status = "failed"
        session.commit()
        session.close()
        return

    print(f"   - Successfully generated {len(questions)} questions.")

    # --- 4. Assign Images & Review ---
    print("\nStep 4: Assigning images and reviewing...")
    used_images = []
    generate_ai_images = config.get("generation", {}).get("generate_ai_images", True)
    prefer_generated_images = config.get("generation", {}).get(
        "prefer_generated_images", False
    )

    # We use a mutable copy of extracted_images to track usage
    available_extracted = extracted_images[:]

    for q_data in questions:
        image_ref = q_data.get("image_ref")

        # Logic to determine if we should assign a NEW image (if none exists or forced)
        should_assign_new = False

        if image_ref:
            # Check if valid extracted image
            # image_ref is basename. Find in available_extracted.
            found_path = None
            for path in available_extracted:
                if os.path.basename(path) == image_ref:
                    found_path = path
                    break

            if found_path:
                if prefer_generated_images and generate_ai_images:
                    # Override extracted with generated
                    image_ref = None
                    should_assign_new = True
                else:
                    # Use the valid extracted image
                    used_images.append((found_path, image_ref))
                    if found_path in available_extracted:
                        available_extracted.remove(found_path)
            else:
                # Image ref not found in extracted
                image_ref = None
                should_assign_new = True
        else:
            # No image ref from generator
            # Check ratio
            if len(used_images) < int(len(questions) * img_ratio):
                should_assign_new = True

        if should_assign_new:
            # Try to assign an image
            use_generated = False
            use_extracted = False

            if prefer_generated_images and generate_ai_images:
                use_generated = True
            elif available_extracted:
                use_extracted = True
            elif generate_ai_images:
                use_generated = True

            if use_generated:
                api_key = os.getenv(
                    "GEMINI_API_KEY"
                )  # Keep for potential Gemini provider if needed
                prompt = q_data.get("text", "A relevant science diagram.")

                # Get Vertex config
                project_id = config.get("llm", {}).get("vertex_project_id")
                location = config.get("llm", {}).get("vertex_location")

                try:
                    gen_path = generate_image(
                        api_key=api_key,
                        prompt=prompt,
                        project_id=project_id,
                        location=location,
                    )
                    image_ref = os.path.basename(gen_path)
                    used_images.append((gen_path, image_ref))
                except Exception as e:
                    print(f"Warning: Image generation failed: {e}")
                    image_ref = None
            elif use_extracted:
                image_path = available_extracted.pop(0)
                image_ref = os.path.basename(image_path)
                used_images.append((image_path, image_ref))
            else:
                # Placeholder
                text_preview = q_data.get("text", "")[:50]
                q_data["image_placeholder"] = (
                    f"Image Recommendation: An image or diagram related to: {text_preview}..."
                )
                image_ref = None

        q_data["image_ref"] = image_ref

    # --- Interactive Review ---
    interactive_mode = config.get("generation", {}).get("interactive_review", True)
    no_interactive = args.no_interactive if hasattr(args, "no_interactive") else False

    if interactive_mode and not no_interactive:

        def regen_callback(q_data):
            api_key = os.getenv(
                "GEMINI_API_KEY"
            )  # Keep for potential Gemini provider if needed
            prompt = q_data.get("text", "A relevant science diagram.")

            # Get Vertex config
            project_id = config.get("llm", {}).get("vertex_project_id")
            location = config.get("llm", {}).get("vertex_location")

            try:
                return generate_image(
                    api_key=api_key,
                    prompt=prompt,
                    project_id=project_id,
                    location=location,
                )
            except Exception as e:
                print(f"Error generating image: {e}")
                return None

        accepted = interactive_review(questions, used_images, config, regen_callback)
        if not accepted:
            print("Quiz generation rejected by user.")
            new_quiz.status = "rejected"
            session.commit()
            session.close()
            return

    # --- Store Questions ---
    for q_data in questions:
        question_record = Question(
            quiz_id=new_quiz.id,
            question_type=q_data.get("type"),
            title=q_data.get("title"),
            text=q_data.get("text"),
            points=q_data.get("points"),
            data=q_data,
        )
        session.add(question_record)

    new_quiz.status = "generated"
    session.commit()
    print(f"   - Stored {len(questions)} questions for Quiz ID: {new_quiz.id}")

    # --- 5. Generate Output Files ---
    print("\nStep 5: Generating output files...")
    db_questions = session.query(Question).filter_by(quiz_id=new_quiz.id).all()
    output_questions = [q.data for q in db_questions]

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    pdf_path = os.path.join(
        config["paths"]["quiz_output_dir"],
        config["qti"]["pdf_filename_template"].format(timestamp=timestamp),
    )

    image_map = {ref: path for path, ref in used_images}
    generate_pdf_preview(
        output_questions, pdf_path, config["generation"]["quiz_title"], image_map
    )
    print(f"   - PDF preview saved to: {pdf_path}")

    qti_path = create_qti_package(output_questions, used_images, config)
    print(f"   - QTI package saved to: {qti_path}")

    session.close()
    print("\n[OK] Generation complete!")


# --- Class Section Handlers ---


def handle_new_class(config, args):
    """Handles the 'new-class' command."""
    engine, session = _get_db_session(config)

    standards = None
    if args.standards:
        standards = [s.strip() for s in args.standards.split(",")]

    new_cls = create_class(
        session,
        name=args.name,
        grade_level=args.grade,
        subject=args.subject,
        standards=standards,
    )
    print(f"Class created: {new_cls.name} (ID: {new_cls.id})")

    if args.grade:
        print(f"   Grade: {args.grade}")
    if args.subject:
        print(f"   Subject: {args.subject}")

    # Ask to set as active
    try:
        print("Set as active class? (yes/no): ", end="")
        response = input().strip().lower()
        if response == "yes":
            set_active_class("config.yaml", new_cls.id)
            print(f"   Active class set to: {new_cls.name}")
    except (EOFError, KeyboardInterrupt):
        pass

    session.close()


def handle_list_classes(config, args):
    """Handles the 'list-classes' command."""
    engine, session = _get_db_session(config)
    active_id = config.get("active_class_id")

    classes = list_classes(session)
    if not classes:
        print("No classes found. Create one with: python main.py new-class --name \"Class Name\"")
        session.close()
        return

    # Print table header
    print(f"\n{'':>2} {'ID':>4}  {'Name':<35} {'Grade':<15} {'Subject':<12} {'Lessons':>7} {'Quizzes':>7}")
    print(f"   {'---':>4}  {'---':<35} {'---':<15} {'---':<12} {'---':>7} {'---':>7}")

    for cls in classes:
        marker = "*" if active_id and int(active_id) == cls["id"] else " "
        name = cls["name"][:33]
        grade = (cls["grade_level"] or "")[:13]
        subject = (cls["subject"] or "")[:10]
        print(
            f"{marker:>2} {cls['id']:>4}  {name:<35} {grade:<15} {subject:<12} "
            f"{cls['lesson_count']:>7} {cls['quiz_count']:>7}"
        )

    print(f"\n   * = active class")
    session.close()


def handle_set_class(config, args):
    """Handles the 'set-class' command."""
    engine, session = _get_db_session(config)

    class_obj = get_class(session, int(args.class_id))
    if not class_obj:
        print(f"Error: Class with ID {args.class_id} not found.")
        print("Use 'python main.py list-classes' to see available classes.")
        session.close()
        return

    success = set_active_class("config.yaml", int(args.class_id))
    if success:
        print(f"Active class set to: {class_obj.name} (ID: {class_obj.id})")
    else:
        print("Error: Could not update config.yaml")

    session.close()


# --- Lesson Tracking Handlers ---


def handle_log_lesson(config, args):
    """Handles the 'log-lesson' command."""
    engine, session = _get_db_session(config)
    class_id = _resolve_class_id(config, args, session)

    class_obj = get_class(session, class_id)
    if not class_obj:
        print(f"Error: Class with ID {class_id} not found.")
        session.close()
        return

    # Build content from --text and/or --file
    content = ""
    if args.file:
        try:
            with open(args.file, "r") as f:
                content = f.read()
        except FileNotFoundError:
            print(f"Error: File not found: {args.file}")
            session.close()
            return
    if args.text:
        if content:
            content += "\n" + args.text
        else:
            content = args.text

    if not content:
        print("Error: Provide lesson content with --text or --file")
        session.close()
        return

    # Parse topics override
    topics = None
    if args.topics:
        topics = [t.strip() for t in args.topics.split(",")]

    lesson = log_lesson(
        session,
        class_id=class_id,
        content=content,
        topics=topics,
        notes=args.notes,
    )

    import json
    lesson_topics = json.loads(lesson.topics) if isinstance(lesson.topics, str) else (lesson.topics or [])

    print(f"Lesson logged for: {class_obj.name}")
    print(f"   Date: {lesson.date}")
    print(f"   Topics: {', '.join(lesson_topics) if lesson_topics else '(none detected)'}")

    # Show knowledge depth changes
    knowledge = get_assumed_knowledge(session, class_id)
    if lesson_topics:
        depth_info = [f"{t}: depth {knowledge.get(t, {}).get('depth', '?')}" for t in lesson_topics]
        print(f"   Knowledge depth: {', '.join(depth_info)}")

    session.close()


def handle_list_lessons(config, args):
    """Handles the 'list-lessons' command."""
    engine, session = _get_db_session(config)
    class_id = _resolve_class_id(config, args, session)

    class_obj = get_class(session, class_id)
    if not class_obj:
        print(f"Error: Class with ID {class_id} not found.")
        session.close()
        return

    # Build filters
    filters = {}
    if args.last:
        filters["last_days"] = int(args.last)
    if hasattr(args, "date_from") and args.date_from:
        filters["date_from"] = date.fromisoformat(args.date_from)
    if hasattr(args, "date_to") and args.date_to:
        filters["date_to"] = date.fromisoformat(args.date_to)
    if args.topic:
        filters["topic"] = args.topic

    lessons = list_lessons(session, class_id, filters if filters else None)

    print(f"\nLessons for: {class_obj.name}")
    if not lessons:
        print("   No lessons found matching filters.")
        session.close()
        return

    import json
    print(f"\n{'Date':<12} {'Topics':<40} {'Notes'}")
    print(f"{'---':<12} {'---':<40} {'---'}")

    for lesson in lessons:
        topics = json.loads(lesson.topics) if isinstance(lesson.topics, str) else (lesson.topics or [])
        topics_str = ", ".join(topics)[:38] if topics else "(none)"
        notes_str = (lesson.notes or "")[:30]
        print(f"{str(lesson.date):<12} {topics_str:<40} {notes_str}")

    print(f"\nTotal lessons: {len(lessons)}")

    # Show assumed knowledge summary
    knowledge = get_assumed_knowledge(session, class_id)
    if knowledge:
        print(f"\nAssumed Knowledge:")
        for topic, data in sorted(knowledge.items(), key=lambda x: x[1]["depth"], reverse=True):
            depth_label = {1: "introduced", 2: "reinforced", 3: "practiced", 4: "mastered", 5: "expert"}.get(
                data["depth"], "unknown"
            )
            print(f"   {topic}: depth {data['depth']} ({depth_label}), last taught {data['last_taught']}")

    session.close()


# --- Cost Tracking Handler ---


def handle_cost_summary(config, args):
    """Handles the 'cost-summary' command."""
    stats = get_cost_summary()
    if stats["total_calls"] == 0:
        print("No API calls recorded. (Using mock provider has zero cost.)")
        return
    print(format_cost_report(stats))


def main():
    load_dotenv()
    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print("Error: config.yaml not found.")
        return

    parser = argparse.ArgumentParser(description="QuizWeaver CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- Ingest Command ---
    subparsers.add_parser(
        "ingest", help="Ingest content from the content directory into the database."
    )

    # --- Generate Command ---
    parser_generate = subparsers.add_parser(
        "generate", help="Generate a new quiz from the content in the database."
    )
    parser_generate.add_argument(
        "--count", type=int, help="Manually specify the number of questions."
    )
    parser_generate.add_argument(
        "--grade", type=str, help="The grade level for the quiz."
    )
    parser_generate.add_argument(
        "--sol", nargs="+", help="A list of SOL standards to focus on."
    )
    parser_generate.add_argument(
        "--no-interactive", action="store_true", help="Skip interactive review."
    )
    parser_generate.add_argument(
        "--class", dest="class_id", type=int, help="Override active class for this generation."
    )

    # --- New Class Command ---
    parser_new_class = subparsers.add_parser(
        "new-class", help="Create a new class/block."
    )
    parser_new_class.add_argument(
        "--name", required=True, help="Name of the class (e.g., '7th Grade Science - Block A')."
    )
    parser_new_class.add_argument(
        "--grade", type=str, help="Grade level (e.g., '7th Grade')."
    )
    parser_new_class.add_argument(
        "--subject", type=str, help="Subject area (e.g., 'Science')."
    )
    parser_new_class.add_argument(
        "--standards", type=str, help="Comma-separated standards (e.g., 'SOL 7.1,SOL 7.2')."
    )

    # --- List Classes Command ---
    subparsers.add_parser(
        "list-classes", help="List all classes/blocks."
    )

    # --- Set Class Command ---
    parser_set_class = subparsers.add_parser(
        "set-class", help="Set the active class for subsequent commands."
    )
    parser_set_class.add_argument(
        "class_id", type=int, help="The ID of the class to set as active."
    )

    # --- Log Lesson Command ---
    parser_log_lesson = subparsers.add_parser(
        "log-lesson", help="Log a lesson taught to a class."
    )
    parser_log_lesson.add_argument(
        "--text", type=str, help="Lesson content text."
    )
    parser_log_lesson.add_argument(
        "--file", type=str, help="Path to file containing lesson content."
    )
    parser_log_lesson.add_argument(
        "--notes", type=str, help="Teacher observations/notes."
    )
    parser_log_lesson.add_argument(
        "--topics", type=str, help="Comma-separated topic overrides."
    )
    parser_log_lesson.add_argument(
        "--class", dest="class_id", type=int, help="Override active class."
    )

    # --- List Lessons Command ---
    parser_list_lessons = subparsers.add_parser(
        "list-lessons", help="List lessons for a class."
    )
    parser_list_lessons.add_argument(
        "--last", type=int, help="Show lessons from last N days."
    )
    parser_list_lessons.add_argument(
        "--from", dest="date_from", type=str, help="Start date (YYYY-MM-DD)."
    )
    parser_list_lessons.add_argument(
        "--to", dest="date_to", type=str, help="End date (YYYY-MM-DD)."
    )
    parser_list_lessons.add_argument(
        "--topic", type=str, help="Filter by topic name."
    )
    parser_list_lessons.add_argument(
        "--class", dest="class_id", type=int, help="Override active class."
    )

    # --- Cost Summary Command ---
    subparsers.add_parser(
        "cost-summary", help="Display API cost summary."
    )

    args = parser.parse_args()

    if args.command == "ingest":
        handle_ingest(config)
    elif args.command == "generate":
        handle_generate(config, args)
    elif args.command == "new-class":
        handle_new_class(config, args)
    elif args.command == "list-classes":
        handle_list_classes(config, args)
    elif args.command == "set-class":
        handle_set_class(config, args)
    elif args.command == "log-lesson":
        handle_log_lesson(config, args)
    elif args.command == "list-lessons":
        handle_list_lessons(config, args)
    elif args.command == "cost-summary":
        handle_cost_summary(config, args)


if __name__ == "__main__":
    main()
