import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

GENERATED_IMAGES_DIR = "generated_images"


def generate_image(api_key, prompt):
    print(f"Placeholder image generation for prompt: '{prompt[:50]}...'")
    return create_placeholder_image(prompt)


def create_placeholder_image(text):
    if not os.path.exists(GENERATED_IMAGES_DIR):
        os.makedirs(GENERATED_IMAGES_DIR)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    filename = f"placeholder_{timestamp}.png"
    filepath = os.path.join(GENERATED_IMAGES_DIR, filename)

    # Create image
    width, height = 400, 300
    img = Image.new("RGB", (width, height), color=(230, 230, 230))
    d = ImageDraw.Draw(img)

    # Draw text
    try:
        # Try to use a standard font if available
        font = ImageFont.truetype("arial.ttf", 14)
        title_font = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        # Fallback to default font
        font = ImageFont.load_default()
        title_font = ImageFont.load_default()

    # Draw Title
    d.text(
        (20, height / 2 - 40), "AI Image Placeholder", fill=(0, 0, 0), font=title_font
    )

    # Wrap text
    margin = 20
    offset = height / 2
    for line in text_wrap(text, font, width - 2 * margin):
        d.text((margin, offset), line, fill=(0, 0, 0), font=font)
        offset += 15

    img.save(filepath)
    return filepath


def text_wrap(text, font, max_width):
    lines = []
    try:
        font.getlength("a")
    except AttributeError:
        # Fallback for very old Pillow or default font limitations
        return [text[i : i + 50] for i in range(0, len(text), 50)]

    words = text.split()
    if not words:
        return []

    current_line = words[0]
    for word in words[1:]:
        if font.getlength(current_line + " " + word) <= max_width:
            current_line += " " + word
        else:
            lines.append(current_line)
            current_line = word
    lines.append(current_line)
    return lines
