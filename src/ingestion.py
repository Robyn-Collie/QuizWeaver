import os
import fitz  # PyMuPDF
from docx import Document
from .database import Lesson, Asset
from .llm_provider import get_provider
import json
from PIL import Image
import io

# Optional: Try importing pdf2image for high-quality rendering
try:
    # from pdf2image import convert_from_path # Removed unused import
    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False
    print(
        "Warning: pdf2image not installed. Falling back to PyMuPDF for image extraction."
    )


def ingest_content(session, config):
    """
    Reads all documents from the content summary directory, processes them,
    and stores them in the database. Supports \"standard\" and \"multimodal\" ingestion.
    """
    content_dir = config["paths"]["content_summary_dir"]
    ingestion_mode = config.get("ingestion", {}).get("mode", "standard")

    # Initialize provider only if needed for multimodal ingestion
    llm_provider = None
    if ingestion_mode == "multimodal":
        try:
            # We explicitly use the Gemini 3 Pro provider for this advanced task
            # Cloning config to force the provider choice locally for this operation
            ingest_config = config.copy()
            if "llm" not in ingest_config:
                ingest_config["llm"] = {}
            ingest_config["llm"]["provider"] = "gemini-3-pro"
            llm_provider = get_provider(ingest_config)
        except Exception as e:
            print(
                f"Failed to initialize multimodal provider: {e}. Falling back to standard ingestion."
            )
            ingestion_mode = "standard"

    for filename in os.listdir(content_dir):
        filepath = os.path.join(content_dir, filename)

        # Check if this file has already been ingested
        existing_lesson = session.query(Lesson).filter_by(source_file=filename).first()

        # If it exists, we might want to re-ingest if we are upgrading to multimodal
        if existing_lesson:
            if existing_lesson.ingestion_method == ingestion_mode:
                print(f"Skipping already ingested file ({ingestion_mode}): {filename}")
                continue
            else:
                print(f"Re-ingesting file {filename} to upgrade to {ingestion_mode}...")
                session.delete(existing_lesson)
                session.commit()

        print(f"Ingesting new file: {filename} [{ingestion_mode}]")

        content_text = ""
        page_data = []  # List to store structured analysis per page

        if filename.endswith(".pdf"):
            if ingestion_mode == "multimodal" and llm_provider:
                content_text, page_data = process_pdf_multimodal(filepath, llm_provider)
            else:
                doc = fitz.open(filepath)
                content_parts = []
                for page in doc:
                    content_parts.append(page.get_text())
                content_text = "\n".join(content_parts)
                doc.close()

        elif filename.endswith(".txt"):
            with open(filepath, "r", encoding="utf-8") as f:
                content_text = f.read()
        elif filename.endswith(".docx"):
            doc = Document(filepath)
            content_parts = []
            for para in doc.paragraphs:
                content_parts.append(para.text)
            content_text = "\n".join(content_parts)

        # Create a new Lesson record
        lesson = Lesson(
            source_file=filename,
            content=content_text,
            page_data=page_data,
            ingestion_method=ingestion_mode,
        )
        session.add(lesson)
        session.commit()  # Commit to get the lesson ID

        # Extract images (legacy method, still useful for referencing specific assets)
        if filename.endswith(".pdf"):
            extract_and_save_images(session, config, lesson, filepath)

    session.commit()
    print("Content ingestion complete.")


def process_pdf_multimodal(filepath, provider):
    """
    Uses a multimodal LLM to analyze each page of a PDF.
    Returns the full text and a list of structured page data objects.
    """
    print("  - Starting multimodal analysis...")
    full_text = []
    structured_pages = []

    # Render PDF pages to images
    # Using PyMuPDF as a reliable fallback/default if pdf2image isn\"t set up
    doc = fitz.open(filepath)

    for page_index in range(len(doc)):
        print(f"  - Analyzing page {page_index + 1}...")
        page = doc[page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better resolution
        img_data = pix.tobytes("png")

        # Construct Prompt for Layout Analysis
        prompt = """
        Analyze this document page image. Return a structured JSON object with the following fields:
        1. "text_content": The full text content of the page.
        2. "headings": A list of section headings found on the page.
        3. "diagrams": A list of objects describing any diagrams, charts, or images. Each object should have:
           - "description": A detailed description of what the diagram shows.
           - "caption": The caption text associated with the diagram (if any).
           - "type": The type of visual (e.g., "chart", "photograph", "diagram").

        Ensure the output is valid JSON.
        """

        # Call the provider
        # We wrap the image bytes in a way the provider expects (handled internally by GenAI SDK usually)
        # For our abstraction, we pass the raw bytes object or PIL image

        # Create a temporary PIL image from bytes to pass to the provider (standard for Gemini)
        img = Image.open(io.BytesIO(img_data))

        response_text = provider.generate([prompt, img], json_mode=True)

        try:
            # Clean up potential markdown code blocks from response
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]

            page_analysis = json.loads(cleaned_text)

            # Aggregate content
            full_text.append(page_analysis.get("text_content", ""))
            structured_pages.append(page_analysis)

        except json.JSONDecodeError:
            print(
                f"    ! Failed to parse JSON for page {page_index + 1}. Fallback to text extraction."
            )
            full_text.append(page.get_text())
            structured_pages.append(
                {"error": "Failed to analyze layout", "page": page_index + 1}
            )

    doc.close()
    return "\n".join(full_text), structured_pages


def extract_and_save_images(session, config, lesson, pdf_path):
    """
    Extracts images from a single PDF and saves them as Asset records.
    """
    images_dir = config["paths"]["extracted_images_dir"]
    if not os.path.exists(images_dir):
        os.makedirs(images_dir)

    doc = fitz.open(pdf_path)
    for page_index in range(len(doc)):
        image_list = doc.get_page_images(page_index, full=True)

        for image_index, img in enumerate(image_list, start=1):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]

            image_filename = f"image_{lesson.id}_{page_index+1}_{image_index}.png"
            image_path = os.path.join(images_dir, image_filename)

            with open(image_path, "wb") as f:
                f.write(image_bytes)

            # Create a new Asset record
            asset = Asset(lesson_id=lesson.id, asset_type="image", path=image_path)
            session.add(asset)
    doc.close()


def get_retake_analysis(config):
    """
    Analyzes the PDF in the \"Retake\" directory to extract its text content and image statistics.
    """
    retake_dir = config["paths"]["retake_dir"]
    retake_texts = []
    total_images_in_retake = 0

    for filename in os.listdir(retake_dir):
        if filename.endswith(".pdf"):
            filepath = os.path.join(retake_dir, filename)
            doc = fitz.open(filepath)
            text = ""
            for page in doc:
                text += page.get_text()
                image_list = page.get_images(full=True)
                if image_list:
                    total_images_in_retake += len(image_list)

            doc.close()
            retake_texts.append(text)

    combined_text = " ".join(retake_texts)

    q_types = [
        "Multiple Choice",
        "True or False",
        "Fill in the Blank",
        "Essay",
        "Multiple Answer",
    ]
    estimated_count = sum(combined_text.count(qt) for qt in q_types)

    if estimated_count == 0:
        estimated_count = 15

    percentage_with_images = 0.0
    if estimated_count > 0:
        percentage_with_images = total_images_in_retake / estimated_count

    return (
        combined_text,
        estimated_count,
        total_images_in_retake,
        percentage_with_images,
    )
