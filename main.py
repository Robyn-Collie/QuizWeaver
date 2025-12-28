import os
import argparse
from dotenv import load_dotenv
import yaml
from datetime import datetime

# Import from our new library structure
from src.ingestion import ingest_content, get_retake_analysis
from src.agents import run_agentic_pipeline
from src.output import generate_pdf_preview, create_qti_package
from src.image_gen import generate_image
from src.database import get_engine, init_db, get_session, Lesson, Asset, Quiz, Question
from src.review import interactive_review


def handle_ingest(config):
    """Handles the "ingest" command."""
    print("--- Starting Content Ingestion ---")
    engine = get_engine(config["paths"]["database_file"])
    init_db(engine)
    session = get_session(engine)
    ingest_content(session, config)
    session.close()
    print("✅ Ingestion complete.")


def handle_generate(config, args):
    """Handles the "generate" command."""
    print("--- Starting Quiz Generation ---")
    engine = get_engine(config["paths"]["database_file"])
    session = get_session(engine)

    # --- 1. Load Data & Analyze ---
    print("Step 1: Loading content and analyzing retake...")
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

    questions = run_agentic_pipeline(config, context)

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
    print("\n✅ Generation complete!")


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

    args = parser.parse_args()

    if args.command == "ingest":
        handle_ingest(config)
    elif args.command == "generate":
        handle_generate(config, args)


if __name__ == "__main__":
    main()
