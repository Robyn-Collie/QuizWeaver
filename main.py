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


def main():
    load_dotenv()

    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print("Error: config.yaml not found.")
        return

    # --- Database Initialization ---
    db_path = config["paths"]["database_file"]
    engine = get_engine(db_path)
    init_db(engine)
    print(f"Database initialized at {db_path}")

    parser = argparse.ArgumentParser(
        description="Generate a retake quiz based on provided content."
    )
    parser.add_argument(
        "--count", type=int, help="Manually specify the number of questions."
    )
    parser.add_argument(
        "--grade",
        type=str,
        help="The grade level for the quiz (e.g., '8th Grade History').",
    )
    parser.add_argument(
        "--sol",
        nargs="+",
        help="A list of SOL standards to focus on (e.g., --sol '6.1' '6.2a').",
    )
    args = parser.parse_args()

    output_dir = config["paths"]["quiz_output_dir"]
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # --- 1. Ingestion Silo ---
    print("Step 1: Ingesting and analyzing content...")
    session = get_session(engine)
    ingest_content(session, config)

    # Query the database to get all lesson content
    all_lessons = session.query(Lesson).all()
    content_summary = "\n".join([lesson.content for lesson in all_lessons])

    # Query for all extracted images
    all_assets = session.query(Asset).filter_by(asset_type="image").all()
    extracted_images = [asset.path for asset in all_assets]

    # The retake analysis is still file-based for now
    retake_text, est_question_count, image_count, image_ratio = get_retake_analysis(
        config
    )

    num_questions = args.count if args.count else est_question_count
    grade_level = (
        args.grade if args.grade else config["generation"]["default_grade_level"]
    )
    sol_standards = args.sol if args.sol else config["generation"]["sol_standards"]

    # --- 2. Create Quiz Record ---
    print("\nStep 2: Creating new quiz record...")
    style_profile = {
        "estimated_question_count": est_question_count,
        "image_ratio": image_ratio,
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
        print(f"   - SOL Standards: {', '.join(sol_standards)}")
    print(f"   - Targeting {num_questions} questions.")

    print("\nStep 3: Generating questions with the AI Agent...")
    generated_questions_str = generate_questions(
        config=config,
        content_summary=content_summary,
        retake_text=retake_text,
        num_questions=num_questions,
        images=extracted_images,
        image_ratio=image_ratio,
        grade_level=grade_level,
        sol_standards=sol_standards,
    )

    try:
        start_index = generated_questions_str.find("[")
        end_index = generated_questions_str.rfind("]")
        if start_index == -1 or end_index == -1:
            raise json.JSONDecodeError(
                "No JSON array found in the model's output.", generated_questions_str, 0
            )

        json_str = generated_questions_str[start_index : end_index + 1]
        questions = json.loads(json_str)
        print(f"   - Successfully generated {len(questions)} questions.")
    except json.JSONDecodeError as e:
        print(f"Error: Could not parse JSON from the AI model. {e}")
        print(
            "--- Raw AI Output ---\n"
            + generated_questions_str
            + "\n---------------------"
        )
        session.close()
        return

    # --- 4. Store Questions and Handle Images ---
    print("\nStep 4: Storing generated questions...")
    used_images = []
    target_image_count = int(len(questions) * image_ratio)

    for q_data in questions:
        # Handle image association first
        image_ref = None
        if len(used_images) < target_image_count:
            if extracted_images:
                image_path = extracted_images.pop(0)
                image_ref = os.path.basename(image_path)
                used_images.append((image_path, image_ref))
            else:
                api_key = os.getenv("GEMINI_API_KEY")  # Still needed for image gen
                prompt = q_data.get("text", "A relevant science diagram.")
                gen_path = generate_image(api_key, prompt)
                image_ref = os.path.basename(gen_path)
                used_images.append((gen_path, image_ref))

        # Create the Question database object
        question_record = Question(
            quiz_id=new_quiz.id,
            question_type=q_data.get("type"),
            title=q_data.get("title"),
            text=q_data.get("text"),
            points=q_data.get("points"),
            data={
                "options": q_data.get("options"),
                "correct_index": q_data.get("correct_index"),
                "is_true": q_data.get("is_true"),
                "image_ref": image_ref,
            },
        )
        session.add(question_record)

    new_quiz.status = "generated"
    session.commit()
    print(f"   - Stored {len(questions)} questions for Quiz ID: {new_quiz.id}")

    # --- 5. Generating output files ---
    print("\nStep 5: Generating output files...")

    # Reload the questions from the DB to ensure we have the latest data
    db_questions = session.query(Question).filter_by(quiz_id=new_quiz.id).all()

    # Re-format for the output functions
    output_questions = []
    for q in db_questions:
        q_dict = {
            "type": q.question_type,
            "title": q.title,
            "text": q.text,
            "points": q.points,
            **q.data,
        }
        output_questions.append(q_dict)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    pdf_filename = os.path.join(
        output_dir, config["qti"]["pdf_filename_template"].format(timestamp=timestamp)
    )
    generate_pdf_preview(
        output_questions, pdf_filename, config["generation"]["quiz_title"]
    )
    print(f"   - PDF preview saved to: {pdf_filename}")

    qti_filename = create_qti_package(output_questions, used_images, config)
    print(f"   - QTI package for Canvas saved to: {qti_filename}")

    session.close()

    print("\n✅ Process complete!")


if __name__ == "__main__":
    main()
