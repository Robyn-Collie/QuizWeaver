import os
import fitz  # PyMuPDF
from docx import Document
from .database import Lesson, Asset


def ingest_content(session, config):
    """
    Reads all documents from the content summary directory, processes them,
    and stores them in the database.
    """
    content_dir = config["paths"]["content_summary_dir"]

    for filename in os.listdir(content_dir):
        filepath = os.path.join(content_dir, filename)

        # Check if this file has already been ingested
        existing_lesson = session.query(Lesson).filter_by(source_file=filename).first()
        if existing_lesson:
            print(f"Skipping already ingested file: {filename}")
            continue

        print(f"Ingesting new file: {filename}")

        content_parts = []

        if filename.endswith(".pdf"):
            doc = fitz.open(filepath)
            for page in doc:
                content_parts.append(page.get_text())
            doc.close()
        elif filename.endswith(".txt"):
            with open(filepath, "r", encoding="utf-8") as f:
                content_parts.append(f.read())
        elif filename.endswith(".docx"):
            doc = Document(filepath)
            for para in doc.paragraphs:
                content_parts.append(para.text)

        full_content = "\n".join(content_parts)

        # Create a new Lesson record
        lesson = Lesson(source_file=filename, content=full_content)
        session.add(lesson)
        session.commit()  # Commit to get the lesson ID

        # Now, extract images and associate them with this lesson
        if filename.endswith(".pdf"):
            extract_and_save_images(session, config, lesson, filepath)

    session.commit()
    print("Content ingestion complete.")


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
    Analyzes the PDF in the 'Retake' directory to extract its text content and image statistics.
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
