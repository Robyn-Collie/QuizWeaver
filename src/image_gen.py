import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import google.generativeai as genai

GENERATED_IMAGES_DIR = "generated_images"

def generate_image(api_key, prompt):
    """
    Generates an image using a placeholder function.
    In a real implementation, this would call an image generation API.
    """
    print(f"Placeholder image generation for prompt: '{prompt[:50]}...'")
    return create_placeholder_image(prompt)

def create_placeholder_image(text):
    """
    Creates a placeholder PNG image with the given text.
    """
    if not os.path.exists(GENERATED_IMAGES_DIR):
        os.makedirs(GENERATED_IMAGES_DIR)
        
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    filename = f"placeholder_{timestamp}.png"
    filepath = os.path.join(GENERATED_IMAGES_DIR, filename)
    
    c = canvas.Canvas(filepath, pagesize=(400, 300))
    c.setFillColorRGB(0.9, 0.9, 0.9)
    c.rect(0, 0, 400, 300, fill=1)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(200, 170, "AI Image Placeholder")
    c.setFont("Helvetica", 10)
    c.drawCentredString(200, 140, "Prompt:")
    c.drawCentredString(200, 125, text[:70])
    c.save()
    
    return filepath
