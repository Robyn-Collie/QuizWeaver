import google.generativeai as genai
import os

def get_qa_guidelines():
    """Reads the QA guidelines from the specified file."""
    try:
        with open("qa_guidelines.txt", "r") as f:
            return f.read()
    except FileNotFoundError:
        print("Warning: qa_guidelines.txt not found.")
        return ""

def generate_questions(api_key, content_summary, retake_text, num_questions, images, image_ratio, grade_level, sol_standards):
    """
    Calls the Gemini API to generate quiz questions based on the provided context.
    This function represents the core of the 'Generator Agent'.
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    qa_guidelines = get_qa_guidelines()
    
    # Dynamically build the SOL standards section
    sol_section = ""
    if sol_standards:
        sol_list = "\n".join([f"- {s}" for s in sol_standards])
        sol_section = f"""**SOL Standards Focus:**
You must generate questions that specifically target the following SOL standards:
{sol_list}
"""

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
    Based on the **Content Summary**, generate exactly {num_questions} unique quiz questions.

    **Exclusions:**
    Do NOT repeat or closely rephrase any questions from the **Previous Test Questions** provided below.

    ---
    **Content Summary:**
    {content_summary}
    ---
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
    
    # Add images to the prompt, if any are available
    for img_path in images:
        try:
            img = genai.upload_file(img_path)
            prompt_parts.append(img)
            prompt_parts.append(f"Context for image: {os.path.basename(img_path)}")
        except Exception as e:
            print(f"Could not upload image {img_path}: {e}")

    try:
        response = model.generate_content(prompt_parts)
        return response.text
    except Exception as e:
        print(f"An error occurred during question generation: {e}")
        return "[]"
