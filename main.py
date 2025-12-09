import os
import argparse
import json
from dotenv import load_dotenv
import yaml
from datetime import datetime

from src.ingestion import get_content_summary, extract_images_from_pdfs, get_retake_analysis
from src.agents import generate_questions
from src.output import generate_pdf_preview, create_qti_package
from src.image_gen import generate_image

def main():
    load_dotenv()

    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print("Error: config.yaml not found.")
        return

    parser = argparse.ArgumentParser(description="Generate a retake quiz based on provided content.")
    parser.add_argument("--count", type=int, help="Manually specify the number of questions.")
    parser.add_argument("--grade", type=str, help="The grade level for the quiz (e.g., '8th Grade History').")
    parser.add_argument("--sol", nargs='+', help="A list of SOL standards to focus on (e.g., --sol '6.1' '6.2a').")
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env file.")
        return

    output_dir = config['paths']['quiz_output_dir']
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print("Step 1: Ingesting and analyzing content...")
    content_summary = get_content_summary()
    extracted_images = extract_images_from_pdfs()
    
    retake_text, est_question_count, image_count, image_ratio = get_retake_analysis()
    
    num_questions = args.count if args.count else est_question_count
    grade_level = args.grade if args.grade else config['generation']['default_grade_level']
    sol_standards = args.sol if args.sol else config['generation']['sol_standards']
    
    print(f"   - Grade Level: {grade_level}")
    if sol_standards:
        print(f"   - SOL Standards: {', '.join(sol_standards)}")
    print(f"   - Targeting {num_questions} questions.")

    print("\nStep 2: Generating questions with the AI Agent...")
    generated_questions_str = generate_questions(
        api_key=api_key,
        content_summary=content_summary,
        retake_text=retake_text,
        num_questions=num_questions,
        images=extracted_images,
        image_ratio=image_ratio,
        grade_level=grade_level,
        sol_standards=sol_standards
    )
    
    try:
        start_index = generated_questions_str.find('[')
        end_index = generated_questions_str.rfind(']')
        if start_index == -1 or end_index == -1:
            raise json.JSONDecodeError("No JSON array found in the model's output.", generated_questions_str, 0)
        
        json_str = generated_questions_str[start_index:end_index+1]
        questions = json.loads(json_str)
        print(f"   - Successfully generated {len(questions)} questions.")
    except json.JSONDecodeError as e:
        print(f"Error: Could not parse JSON from the AI model. {e}")
        print("--- Raw AI Output ---\n" + generated_questions_str + "\n---------------------")
        return

    used_images = []
    target_image_count = int(len(questions) * image_ratio)
    
    for q in questions:
        if len(used_images) < target_image_count:
            if extracted_images:
                image_path = extracted_images.pop(0)
                image_filename = os.path.basename(image_path)
                q["image_ref"] = image_filename
                used_images.append((image_path, image_filename))
            else:
                prompt = q.get("text", "A relevant science diagram.")
                gen_path = generate_image(api_key, prompt)
                gen_filename = os.path.basename(gen_path)
                q["image_ref"] = gen_filename
                used_images.append((gen_path, gen_filename))

    print("\nStep 3: Generating output files...")
    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    pdf_filename = os.path.join(output_dir, config['qti']['pdf_filename_template'].format(timestamp=timestamp))
    generate_pdf_preview(questions, pdf_filename, config['generation']['quiz_title'])
    print(f"   - PDF preview saved to: {pdf_filename}")
    
    qti_filename = create_qti_package(questions, used_images, config)
    print(f"   - QTI package for Canvas saved to: {qti_filename}")
    
    print("\n✅ Process complete!")

if __name__ == "__main__":
    main()
