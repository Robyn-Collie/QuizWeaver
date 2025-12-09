import os
import fitz  # PyMuPDF
from docx import Document

# These will be loaded from config
CONTENT_SUMMARY_DIR = "Content_Summary"
RETAKE_DIR = "Retake"
EXTRACTED_IMAGES_DIR = "extracted_images"

def get_content_summary():
    """
    Reads all documents from the content summary directory and combines them into a single string.
    Supports .pdf, .docx, and .txt files.
    """
    content_summary = []
    for filename in os.listdir(CONTENT_SUMMARY_DIR):
        filepath = os.path.join(CONTENT_SUMMARY_DIR, filename)
        if filename.endswith(".pdf"):
            doc = fitz.open(filepath)
            for page in doc:
                content_summary.append(page.get_text())
            doc.close()
        elif filename.endswith(".txt"):
            with open(filepath, "r", encoding="utf-8") as f:
                content_summary.append(f.read())
        elif filename.endswith(".docx"):
            doc = Document(filepath)
            for para in doc.paragraphs:
                content_summary.append(para.text)

    return " ".join(content_summary)

def extract_images_from_pdfs():
    """
    Extracts images from all PDFs in the content summary directory.
    
    Returns:
        list: A list of file paths to the extracted images.
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
                image_list = page.get_images(full=True)
                
                for image_index, img in enumerate(image_list, start=1):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    
                    image_filename = f"image_{filename}_{page_index+1}_{image_index}.png"
                    image_path = os.path.join(EXTRACTED_IMAGES_DIR, image_filename)
                    
                    with open(image_path, "wb") as f:
                        f.write(image_bytes)
                        
                    extracted_images.append(image_path)
            doc.close()
            
    return extracted_images

def get_retake_analysis():
    """
    Analyzes the PDF in the 'Retake' directory to extract its text content and image statistics.
    This function serves as the basis for the Analyst Agent's capabilities.
    
    Returns:
        tuple: A tuple containing:
            - str: The combined text of the retake documents.
            - int: The estimated number of questions.
            - int: The total number of images found.
            - float: The percentage of questions that have images.
    """
    retake_texts = []
    total_images_in_retake = 0
    
    for filename in os.listdir(RETAKE_DIR):
        if filename.endswith(".pdf"):
            filepath = os.path.join(RETAKE_DIR, filename)
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
    
    # A simple heuristic to estimate question count for style analysis.
    # In a real scenario, a more robust NLP model would be used here.
    q_types = ["Multiple Choice", "True or False", "Fill in the Blank", "Essay", "Multiple Answer"]
    estimated_count = sum(combined_text.count(qt) for qt in q_types)
        
    if estimated_count == 0:
        # Fallback if no question types are explicitly mentioned.
        # This could be improved with better heuristics (e.g., counting numbered lists).
        estimated_count = 15 
    
    percentage_with_images = 0.0
    if estimated_count > 0:
        percentage_with_images = (total_images_in_retake / estimated_count)
        
    return combined_text, estimated_count, total_images_in_retake, percentage_with_images
