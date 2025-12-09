import zipfile
import os
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv
import fitz  # PyMuPDF
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import io
import argparse
from docx import Document

load_dotenv()

# --- Configuration ---
QUIZ_TITLE = "Change Over Time Test (Retake)"
ZIP_FILENAME_TEMPLATE = "ChangeOverTime_Retake_{timestamp}.zip"
PDF_FILENAME_TEMPLATE = "ChangeOverTime_Retake_{timestamp}.pdf"
MANIFEST_NAME = "imsmanifest.xml"
ASSESSMENT_FILENAME = "quiz_content.xml"
CONTENT_SUMMARY_DIR = "Content_Summary"
RETAKE_DIR = "Retake"
QUIZ_OUTPUT_DIR = "Quiz_Output"
EXTRACTED_IMAGES_DIR = "extracted_images"
GENERATED_IMAGES_DIR = "generated_images"

# --- QTI XML Templates ---

MANIFEST_TEMPLATE_START = """<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="man_{manifest_id}" xmlns="http://www.imsglobal.org/xsd/imscp_v1p1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.imsglobal.org/xsd/imscp_v1p1 http://www.imsglobal.org/xsd/imscp_v1p1.xsd">
  <metadata>
    <schema>IMS Content</schema>
    <schemaversion>1.1.3</schemaversion>
  </metadata>
  <organizations />
  <resources>
    <resource identifier="res_{assessment_id}" type="imsqti_xmlv1p2/imscc_xmlv1p1/assessment">
      <file href="{assessment_filename}"/>"""

MANIFEST_TEMPLATE_END = """
    </resource>
  </resources>
</manifest>"""

ASSESSMENT_HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<questestinterop xmlns="http://www.imsglobal.org/xsd/ims_qtiasiv1p2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.imsglobal.org/xsd/ims_qtiasiv1p2 http://www.imsglobal.org/xsd/ims_qtiasiv1p2.xsd">
  <assessment ident="{assessment_id}" title="{title}">
    <qtimetadata>
      <qtimetadatafield>
        <fieldlabel>qmd_assessmenttype</fieldlabel>
        <fieldentry>Examination</fieldentry>
      </qtimetadatafield>
    </qtimetadata>
    <section ident="root_section">
"""

ASSESSMENT_FOOTER = """    </section>
  </assessment>
</questestinterop>"""

def create_item_header(ident, title, points, image_ref=None):
    img_tag = ""
    if image_ref:
        img_tag = f'<p><img src="{image_ref}" alt="Question Image"/></p>'
    
    return f"""
      <item ident="{ident}" title="{title}">
        <itemmetadata>
          <qtimetadata>
            <qtimetadatafield>
              <fieldlabel>question_type</fieldlabel>
              <fieldentry>{{qt}}</fieldentry>
            </qtimetadatafield>
            <qtimetadatafield>
              <fieldlabel>points_possible</fieldlabel>
              <fieldentry>{points}</fieldentry>
            </qtimetadatafield>
          </qtimetadata>
        </itemmetadata>
        <presentation>
          <material>
            <mattext texttype="text/html">{img_tag}{{question_text}}</mattext>
          </material>
          {{response_block}}
        </presentation>
        <resprocessing>
          <outcomes>
            <decvar maxvalue="100" minvalue="0" varname="SCORE" vartype="Decimal"/>
          </outcomes>
          {{processing_block}}
        </resprocessing>
      </item>"""

def create_mc_question(id, title, text, points, options, correct_index, image_ref=None):
    response_labels = ""
    for idx, opt in enumerate(options):
        response_labels += f"""
          <response_label ident="opt_{idx}">
            <material><mattext texttype="text/plain">{opt}</mattext></material>
          </response_label>"""
    
    response_block = f"""<response_lid ident="response1" rcardinality="Single">
            <render_choice>
              {response_labels}
            </render_choice>
          </response_lid>"""
    
    processing_block = f"""<respcondition continue="No">
            <conditionvar>
              <varequal respident="response1">opt_{correct_index}</varequal>
            </conditionvar>
            <setvar action="Set" varname="SCORE">{points}</setvar>
          </respcondition>"""
    
    template = create_item_header(id, title, points, image_ref)
    return template.format(qt="multiple_choice_question", question_text=text, response_block=response_block, processing_block=processing_block)

def create_tf_question(id, title, text, points, is_true, image_ref=None):
    return create_mc_question(id, title, text, points, ["True", "False"], 0 if is_true else 1, image_ref)

def create_essay_question(id, title, text, points, image_ref=None):
    response_block = """<response_str ident="response1" rcardinality="Single">
            <render_fib>
              <response_label ident="answer1"/>
            </render_fib>
          </response_str>"""
    
    processing_block = f"""<respcondition continue="No">
            <conditionvar>
              <other/>
            </conditionvar>
            <setvar action="Set" varname="SCORE">0</setvar>
          </respcondition>"""
          
    template = create_item_header(id, title, points, image_ref)
    return template.format(qt="essay_question", question_text=text, response_block=response_block, processing_block=processing_block)

def create_fill_blank_question(id, title, text, points, correct_text, image_ref=None):
    response_block = """<response_str ident="response1" rcardinality="Single">
            <render_fib>
              <response_label ident="answer1" rshuffle="Yes"/>
            </render_fib>
          </response_str>"""
          
    processing_block = f"""<respcondition continue="No">
            <conditionvar>
              <varequal respident="response1" case="No">{correct_text}</varequal>
            </conditionvar>
            <setvar action="Set" varname="SCORE">{points}</setvar>
          </respcondition>"""
    
    template = create_item_header(id, title, points, image_ref)
    return template.format(qt="short_answer_question", question_text=text, response_block=response_block, processing_block=processing_block)

def create_multiple_answer_question(id, title, text, points, options, correct_indices, image_ref=None):
    response_labels = ""
    for idx, opt in enumerate(options):
        response_labels += f"""
          <response_label ident="opt_{idx}">
            <material><mattext texttype="text/plain">{opt}</mattext></material>
          </response_label>"""
    
    response_block = f"""<response_lid ident="response1" rcardinality="Multiple">
            <render_choice>
              {response_labels}
            </render_choice>
          </response_lid>"""
    
    conditions = ""
    for idx in range(len(options)):
        if idx in correct_indices:
            conditions += f"<varequal respident='response1'>opt_{idx}</varequal>"
        else:
            conditions += f"<not><varequal respident='response1'>opt_{idx}</varequal></not>"
            
    processing_block = f"""<respcondition continue="No">
            <conditionvar>
              <and>
                {conditions}
              </and>
            </conditionvar>
            <setvar action="Set" varname="SCORE">{points}</setvar>
          </respcondition>"""

    template = create_item_header(id, title, points, image_ref)
    return template.format(qt="multiple_answers_question", question_text=text, response_block=response_block, processing_block=processing_block)

def extract_images_from_pdfs():
    """
    Extracts images from PDFs in the content summary directory.
    Returns a list of image file paths.
    """
    if not os.path.exists(EXTRACTED_IMAGES_DIR):
        os.makedirs(EXTRACTED_IMAGES_DIR)
        
    extracted_images = []
    
    for filename in os.listdir(CONTENT_SUMMARY_DIR):
        if filename.endswith(".pdf"):
            pdf_path = os.path.join(CONTENT_SUMMARY_DIR, filename)
            doc = fitz.open(pdf_path)
            for page_index in range(len(doc)):
                page = doc[page_index]
                image_list = page.get_images()
                
                for image_index, img in enumerate(image_list, start=1):
                    xref = img[0]
                    pix = fitz.Pixmap(doc, xref)
                    
                    if pix.n - pix.alpha > 3: # CMYK: convert to RGB first
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                        
                    image_filename = f"image_{filename}_{page_index+1}_{image_index}.png"
                    image_path = os.path.join(EXTRACTED_IMAGES_DIR, image_filename)
                    pix.save(image_path)
                    extracted_images.append(image_path)
                    pix = None
            doc.close()
    return extracted_images

def generate_image(api_key, prompt):
    """
    Generates an image using the Gemini API (Imagen).
    """
    # Currently, the google-generativeai library version installed does not support ImageGenerationModel directly.
    # We will use a placeholder image for now to ensure the process completes.
    
    print(f"API-based image generation not available. Creating placeholder for: '{prompt[:30]}...'")
    return create_placeholder_image(prompt)

def create_placeholder_image(text):
    if not os.path.exists(GENERATED_IMAGES_DIR):
        os.makedirs(GENERATED_IMAGES_DIR)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    filename = f"placeholder_{timestamp}.png"
    filepath = os.path.join(GENERATED_IMAGES_DIR, filename)
    
    c = canvas.Canvas(filepath, pagesize=(400, 300))
    c.setFillColorRGB(0.9, 0.9, 0.9)
    c.rect(0, 0, 400, 300, fill=1)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 12)
    c.drawCentredString(200, 150, "Image Generation Placeholder")
    c.setFont("Helvetica", 10)
    c.drawCentredString(200, 130, text[:50] + "...")
    c.save()
    return filepath

def get_retake_questions_count_and_image_stats():
    """
    Scans the RETAKE_DIR for PDFs, extracts text, and attempts to count questions and images.
    Returns: retake_text, question_count, image_count, percentage_with_images
    """
    retake_questions = []
    question_count = 0
    total_images_in_retake = 0
    
    for filename in os.listdir(RETAKE_DIR):
        if filename.endswith(".pdf"):
            filepath = os.path.join(RETAKE_DIR, filename)
            doc = fitz.open(filepath)
            text = ""
            for page in doc:
                text += page.get_text()
                # Count images on this page
                image_list = page.get_images()
                if image_list:
                    total_images_in_retake += len(image_list)
                    
            doc.close()
            retake_questions.append(text)

    combined_text = " ".join(retake_questions)
    
    # Improved counting based on the sample text provided earlier
    # "Multiple Choice5 points", "True or False5 points", "Fill in the Blank5 points"
    q_types = ["Multiple Choice", "True or False", "Fill in the Blank", "Essay", "Multiple Answer"]
    estimated_count = 0
    for qt in q_types:
        estimated_count += combined_text.count(qt)
        
    if estimated_count == 0:
        estimated_count = 15 # Default fallback
    
    # Avoid division by zero
    percentage_with_images = 0
    if estimated_count > 0:
        percentage_with_images = int((total_images_in_retake / estimated_count) * 100)
        
    return " ".join(retake_questions), estimated_count, total_images_in_retake, percentage_with_images

def get_content_summary():
    content_summary = []
    for filename in os.listdir(CONTENT_SUMMARY_DIR):
        filepath = os.path.join(CONTENT_SUMMARY_DIR, filename)
        if filename.endswith(".pdf"):
            doc = fitz.open(filepath)
            for page in doc:
                content_summary.append(page.get_text())
            doc.close()
        elif filename.endswith(".txt"):
            with open(filepath, "r") as f:
                content_summary.append(f.read())
        elif filename.endswith(".docx"):
            doc = Document(filepath)
            for para in doc.paragraphs:
                content_summary.append(para.text)

    return " ".join(content_summary)

def get_qa_guidelines():
    try:
        with open("qa_guidelines.txt", "r") as f:
            return f.read()
    except FileNotFoundError:
        return ""

def generate_questions_from_gemini(api_key, content_summary, retake_questions, num_questions, images, percentage_with_images):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    qa_guidelines = get_qa_guidelines()
    
    prompt_parts = [
        f"""
        You are a 7th Grade Science teacher creating a retake quiz.
        
        **CRITICAL INSTRUCTIONS:**
        {qa_guidelines}
        
        **Rigor & Structure:**
        - Ensure the level of difficulty matches the original test (7th grade science).
        - **Image Requirement:** The original test had images in approximately {percentage_with_images}% of the questions. 
          Please strive to use the provided images as context for roughly {percentage_with_images}% of your generated questions to match this style.
        
        **Task:**
        Based on the content summary below, generate a set of {num_questions} quiz questions.
        
        **Exclusions:**
        Do NOT repeat any of the following questions from the previous test:
        {retake_questions}
        
        **Content Summary:**
        {content_summary}
        
        If you are provided with images, you can reference them in your questions.
        
        Please provide the questions in a structured JSON format. 
        DO NOT include Fill-in-the-Blank questions.
        Use "mc" for Multiple Choice and "tf" for True/False.
        
        Format example:
        
        [
            {{
                "type": "mc",
                "title": "Question Title",
                "text": "Question Text",
                "points": 5,
                "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
                "correct_index": 0
            }},
            {{
                "type": "tf",
                "title": "Question Title",
                "text": "Question Text",
                "points": 5,
                "is_true": true
            }}
        ]
        """
    ]
    
    # Add images to the prompt
    for img_path in images[:5]: # Limit to first 5 images
        try:
            img = genai.upload_file(img_path)
            prompt_parts.append(img)
            prompt_parts.append("Image context.")
        except Exception as e:
            print(f"Could not upload image {img_path}: {e}")

    # Combine text prompt
    final_prompt = [prompt_parts[0]] # Text prompt
    
    # Add the uploaded file objects
    for item in prompt_parts[1:]:
        final_prompt.append(item)

    response = model.generate_content(final_prompt)
    return response.text

def generate_pdf_preview(questions, filename):
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    y_position = height - 50
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y_position, QUIZ_TITLE)
    y_position -= 30
    
    c.setFont("Helvetica", 12)
    
    for i, q in enumerate(questions):
        if y_position < 100:
            c.showPage()
            y_position = height - 50
            
        q_text = q.get("text", "")
        q_type = q.get("type", "")
        q_title = q.get("title", f"Question {i+1}")
        q_points = q.get("points", 5)
        
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y_position, f"{i+1}. {q_title} ({q_points} points)")
        y_position -= 20
        
        c.setFont("Helvetica", 10)
        
        # Handle simple text wrapping
        text_object = c.beginText(50, y_position)
        text_object.setFont("Helvetica", 10)
        
        words = q_text.split()
        line = ""
        for word in words:
            if c.stringWidth(line + " " + word) < 500:
                line += " " + word
            else:
                text_object.textLine(line)
                y_position -= 12
                line = word
        text_object.textLine(line)
        y_position -= 12
        c.drawText(text_object)
        y_position -= 10
        
        # Show options/answer based on type
        if q_type == "mc":
            options = q.get("options", [])
            correct_idx = q.get("correct_index", -1)
            for idx, opt in enumerate(options):
                prefix = "[x]" if idx == correct_idx else "[ ]"
                c.drawString(70, y_position, f"{prefix} {opt}")
                y_position -= 15
        elif q_type == "tf":
            is_true = q.get("is_true", False)
            c.drawString(70, y_position, f"[x] True" if is_true else "[ ] True")
            y_position -= 15
            c.drawString(70, y_position, f"[x] False" if not is_true else "[ ] False")
            y_position -= 15
        elif q_type == "fib":
            correct = q.get("correct_text", "")
            c.drawString(70, y_position, f"Answer: {correct}")
            y_position -= 15
        elif q_type == "ma":
            options = q.get("options", [])
            correct_indices = q.get("correct_indices", [])
            for idx, opt in enumerate(options):
                prefix = "[x]" if idx in correct_indices else "[ ]"
                c.drawString(70, y_position, f"{prefix} {opt}")
                y_position -= 15
        
        y_position -= 20
        
    c.save()
    print(f"PDF Preview saved to {filename}")

def generate_quiz():
    parser = argparse.ArgumentParser(description="Generate a retake quiz.")
    parser.add_argument("--count", type=int, help="Number of questions to generate. Defaults to the number of questions in the retake PDF.")
    args = parser.parse_args()

    if not os.path.exists(QUIZ_OUTPUT_DIR):
        os.makedirs(QUIZ_OUTPUT_DIR)

    manifest_id = uuid.uuid4().hex
    assessment_id = uuid.uuid4().hex
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env file.")
        return
        
    retake_questions_text, estimated_count, image_count, percentage_with_images = get_retake_questions_count_and_image_stats()
    content_summary = get_content_summary()
    extracted_images = extract_images_from_pdfs()
    
    num_questions = args.count if args.count else estimated_count
    print(f"Generating {num_questions} questions...")
    print(f"Original test had {image_count} images ({percentage_with_images}% of questions). Targeting similar ratio.")
    
    generated_questions_str = generate_questions_from_gemini(api_key, content_summary, retake_questions_text, num_questions, extracted_images, percentage_with_images)
    
    try:
        start_index = generated_questions_str.find('[')
        end_index = generated_questions_str.rfind(']')
        generated_questions_str = generated_questions_str[start_index:end_index+1]
        import json
        generated_questions = json.loads(generated_questions_str)
    except (json.JSONDecodeError, IndexError) as e:
        print(f"Error parsing the generated questions: {e}")
        print("Raw output:", generated_questions_str)
        return

    # Generate PDF Preview
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    pdf_filename = os.path.join(QUIZ_OUTPUT_DIR, PDF_FILENAME_TEMPLATE.format(timestamp=timestamp))
    generate_pdf_preview(generated_questions, pdf_filename)

    questions = []
    used_images = []
    manifest_file_entries = ""
    
    # Calculate how many questions need images
    target_image_count = int(len(generated_questions) * (percentage_with_images / 100))
    current_image_count = 0
    available_images = list(extracted_images) # Copy
    
    for i, q in enumerate(generated_questions):
        q_id = f"q{i+1}"
        
        image_ref = None
        # Determine if this question should have an image to meet stats
        # Distribute strictly until target is met? Or assume the model didn't provide specific instructions so we assign round-robin.
        if current_image_count < target_image_count:
            if available_images:
                # Use an extracted image
                image_path = available_images.pop(0)
                image_filename = os.path.basename(image_path)
                image_ref = image_filename
                
                # Store for zip processing
                used_images.append((image_path, image_filename))
                current_image_count += 1
            else:
                # Generate a new image
                # Use question text as prompt
                print(f"Generating image for question {i+1}...")
                generated_path = generate_image(api_key, q.get("text", "Science concept"))
                if generated_path:
                    image_filename = os.path.basename(generated_path)
                    image_ref = image_filename
                    used_images.append((generated_path, image_filename))
                    current_image_count += 1

        if q["type"] == "mc":
            questions.append(create_mc_question(q_id, q.get("title", "Question"), q.get("text", ""), q.get("points", 5), q.get("options", []), q.get("correct_index", 0), image_ref))
        elif q["type"] == "tf":
            questions.append(create_tf_question(q_id, q.get("title", "Question"), q.get("text", ""), q.get("points", 5), q.get("is_true", True), image_ref))
        elif q["type"] == "essay":
            questions.append(create_essay_question(q_id, q.get("title", "Question"), q.get("text", ""), q.get("points", 5), image_ref))
        elif q["type"] == "fib":
            correct_text = q.get("correct_text", q.get("answer", "answer"))
            questions.append(create_fill_blank_question(q_id, q.get("title", "Question"), q.get("text", ""), q.get("points", 5), correct_text, image_ref))
        elif q["type"] == "ma":
            questions.append(create_multiple_answer_question(q_id, q.get("title", "Question"), q.get("text", ""), q.get("points", 5), q.get("options", []), q.get("correct_indices", []), image_ref))

    # Assemble XML
    quiz_content = ASSESSMENT_HEADER.format(assessment_id=assessment_id, title=QUIZ_TITLE)
    quiz_content += "\\n".join(questions)
    quiz_content += ASSESSMENT_FOOTER
    
    # Build Manifest
    manifest_content = MANIFEST_TEMPLATE_START.format(manifest_id=manifest_id, assessment_id=assessment_id, assessment_filename=ASSESSMENT_FILENAME)
    for _, img_name in used_images:
        manifest_content += f'\\n      <file href="{img_name}"/>'
    manifest_content += MANIFEST_TEMPLATE_END
    
    # Write Zip
    zip_filename = os.path.join(QUIZ_OUTPUT_DIR, ZIP_FILENAME_TEMPLATE.format(timestamp=timestamp))
    
    with zipfile.ZipFile(zip_filename, 'w') as zipf:
        zipf.writestr(MANIFEST_NAME, manifest_content)
        zipf.writestr(ASSESSMENT_FILENAME, quiz_content)
        for img_path, img_name in used_images:
            zipf.write(img_path, img_name)
    
    print(f"Successfully created {zip_filename}")
    print("Upload this file to Canvas via Settings -> Import Course Content -> QTI .zip file")

if __name__ == "__main__":
    generate_quiz()
