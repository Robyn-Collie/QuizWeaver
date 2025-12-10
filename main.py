import os
import argparse
import json
from dotenv import load_dotenv
import yaml
from datetime import datetime

# Import from our new library structure
from src.ingestion import ingest_content, get_retake_analysis
from src.agents import generate_questions
from src.output import generate_pdf_preview, create_qti_package
from src.image_gen import generate_image
from src.database import get_engine, init_db, get_session, Lesson, Asset, Quiz, Question


def handle_ingest(config):
    """Handles the \"ingest\" command."""
    print("--- Starting Content Ingestion ---")
    engine = get_engine(config["paths"]["database_file"])
    init_db(engine)
    session = get_session(engine)
    ingest_content(session, config)
    session.close()
    print("✅ Ingestion complete.")


def handle_generate(config, args):
    """Handles the \"generate\" command."""
    print("--- Starting Quiz Generation ---")
    engine = get_engine(config["paths"]["database_file"])
    session = get_session(engine)

    # --- 1. Load Data & Analyze ---
    print("Step 1: Loading content and analyzing retake...")
    all_lessons = session.query(Lesson).all()
    content_summary = "\n".join([lesson.content for lesson in all_lessons])

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
        print(f"   - SOL Standards: {", ".join(sol_standards)}")
    print(f"   - Targeting {num_questions} questions.")

    print("\nStep 3: Generating questions with AI Agent...")
    generated_questions_raw = generate_questions(
        config=config,
        content_summary=content_summary,
        retake_text=retake_text,
        num_questions=num_questions,
        images=extracted_images,
        image_ratio=img_ratio,
        grade_level=grade_level,
        sol_standards=sol_standards,
    )

    try:
        questions = json.loads(
            generated_questions_raw[
                generated_questions_raw.find("[") : generated_questions_raw.rfind("]")
                + 1
            ]
        )
        print(f"   - Successfully generated {len(questions)} questions.")
    except json.JSONDecodeError:
        print("Error: Could not parse JSON from the AI model.")
        new_quiz.status = "failed"
        session.commit()
        session.close()
        return

    # --- 4. Store Questions ---
    print("\nStep 4: Storing generated questions...")
    used_images = []

    for q_data in questions:
        image_ref = None
        if len(used_images) < int(len(questions) * img_ratio):
            if extracted_images:
                image_path = extracted_images.pop(0)
                image_ref = os.path.basename(image_path)
                used_images.append((image_path, image_ref))
            else:
                api_key = os.getenv("GEMINI_API_KEY")
                prompt = q_data.get("text", "A relevant science diagram.")
                gen_path = generate_image(api_key, prompt)
                image_ref = os.path.basename(gen_path)
                used_images.append((gen_path, image_ref))

        q_data["image_ref"] = image_ref

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
    generate_pdf_preview(output_questions, pdf_path, config["generation"]["quiz_title"])
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

    args = parser.parse_args()

    if args.command == "ingest":
        handle_ingest(config)
    elif args.command == "generate":
        handle_generate(config, args)


if __name__ == "__main__":
    main()
