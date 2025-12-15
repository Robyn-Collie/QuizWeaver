import os
from src.llm_provider import get_provider
import json


def get_qa_guidelines():
    """Reads the QA guidelines from the specified file."""
    try:
        with open("qa_guidelines.txt", "r") as f:
            return f.read()
    except FileNotFoundError:
        print("Warning: qa_guidelines.txt not found.")
        return ""


def generate_questions(
    config,
    content_summary,
    structured_data,
    retake_text,
    num_questions,
    images,
    image_ratio,
    grade_level,
    sol_standards,
):
    """
    Calls the configured LLM provider to generate quiz questions.
    """
    llm_provider = get_provider(config)

    qa_guidelines = get_qa_guidelines()

    sol_section = ""
    if sol_standards:
        sol_list = "\n".join([f"- {s}" for s in sol_standards])
        sol_section = f"""**SOL Standards Focus:**
You must generate questions that specifically target the following SOL standards:
{sol_list}
"""

    structured_content_text = ""
    if structured_data:
        structured_content_text = (
            "**Structured Content Analysis (Headings, Diagrams, Layout):**\n"
        )
        structured_content_text += json.dumps(structured_data, indent=2)
        structured_content_text += "\n---\n"

    prompt = f"""
    You are a {grade_level} teacher creating a retake quiz.

    {sol_section}

    **CRITICAL INSTRUCTIONS:**
    {qa_guidelines}

    **Rigor & Structure:**
    - The quiz must be at a {grade_level} level.
    - **Image Requirement:** The original test had images in approximately {int(image_ratio * 100)}% of questions.
      You MUST use the provided images as context for a similar percentage of your generated questions.

    **Task:**
    Based on the **Content Summary** and **Structured Analysis** (if provided), generate exactly {num_questions} unique quiz questions.
    Use the structured data to identify diagrams or specific sections that are key to the lesson.

    **Exclusions:**
    Do NOT repeat or closely rephrase any questions from the **Previous Test Questions** provided below.

    ---
    **Content Summary:**
    {content_summary}
    ---
    {structured_content_text}
    **Previous Test Questions:**
    {retake_text}
    ---

    **Output Format:**
    Provide the output as a structured JSON list. Do not include any text or markdown before or after the JSON.
    Use "mc" for Multiple Choice, "tf" for True/False, and "ma" for Multiple Answer.

    Example:
    [
        {{
            "type": "mc",
            "title": "Cell Organelles",
            "text": "Which organelle is known as the powerhouse of the cell?",
            "points": 5,
            "options": ["Nucleus", "Ribosome", "Mitochondrion", "Cell Wall"],
            "correct_index": 2
        }},
        {{
            "type": "tf",
            "title": "Photosynthesis",
            "text": "Photosynthesis occurs primarily in the roots of a plant.",
            "points": 5,
            "is_true": false
        }}
    ]
    """

    prompt_parts = [prompt]

    for img_path in images:
        try:
            img_context = llm_provider.prepare_image_context(img_path)
            prompt_parts.append(img_context)
            prompt_parts.append(f"Context for image: {os.path.basename(img_path)}")
        except Exception as e:
            print(f"Could not prepare image context for {img_path}: {e}")

    return llm_provider.generate(prompt_parts)
