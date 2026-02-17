import os

from src.export import generate_pdf_preview


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_summary(questions, used_images):
    print("\n--- Quiz Draft Review ---")
    for i, q in enumerate(questions):
        title = q.get("title", f"Question {i + 1}")
        text = q.get("text", "")

        img_ref = q.get("image_ref")
        img_status = "No Image"
        if img_ref:
            img_status = f"Image: {img_ref}"
        elif q.get("image_placeholder"):
            img_status = "Placeholder"

        print(f"\n{i + 1}. [{title}] ({img_status})")
        print(f"   {text}")

        # Show options if available
        options = q.get("options", [])
        if isinstance(options, list):
            for idx, opt in enumerate(options):
                print(f"   {chr(65 + idx)}. {opt}")

        if "correct_answer" in q:
            print(f"   Answer: {q['correct_answer']}")
        elif "correct_index" in q:
            print(f"   Answer: {chr(65 + q['correct_index'])}")

    print("\n-------------------------\n")


def interactive_review(questions, used_images, config, regenerate_callback):
    """
    Interactive loop for reviewing questions.
    Returns True if accepted, False if rejected.
    """
    # Initial PDF generation
    draft_filename = "draft_preview.pdf"
    image_map = {ref: path for path, ref in used_images}

    while True:
        # Generate/Update PDF Preview
        try:
            generate_pdf_preview(questions, draft_filename, "Draft Quiz Preview", image_map)
            print(f"\n[Preview] Draft PDF generated: {os.path.abspath(draft_filename)}")
            print("Please open this file to review the quiz layout and images.")
        except Exception as e:
            print(f"Warning: Could not generate preview PDF: {e}")

        print_summary(questions, used_images)

        print("Options:")
        print("  A - Accept and Save")
        print("  R - Reject and Exit")
        print("  G [N] - Generate/Regenerate Image for Question N")

        choice = input("Enter choice: ").strip().upper()

        if choice == "A":
            return True
        elif choice == "R":
            return False
        elif choice.startswith("G"):
            try:
                parts = choice.split()
                if len(parts) < 2:
                    print("Error: Specify question number (e.g., G 1)")
                    continue
                q_idx = int(parts[1]) - 1
                if 0 <= q_idx < len(questions):
                    print(f"Regenerating image for Question {q_idx + 1}...")
                    new_img_path = regenerate_callback(questions[q_idx])
                    if new_img_path:
                        # Update question record
                        questions[q_idx]["image_ref"] = os.path.basename(new_img_path)
                        if "image_placeholder" in questions[q_idx]:
                            del questions[q_idx]["image_placeholder"]

                        # Update used_images and image_map
                        new_basename = os.path.basename(new_img_path)
                        if (new_img_path, new_basename) not in used_images:
                            used_images.append((new_img_path, new_basename))
                        image_map[new_basename] = new_img_path

                        print(f"Image updated: {new_basename}")
                    else:
                        print("Image generation failed.")
                else:
                    print("Invalid question number.")
            except ValueError:
                print("Invalid input.")
        else:
            print("Unknown command.")
