import zipfile
import os
import uuid
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


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


def create_item_header(ident, title, points, image_ref=None, image_placeholder=None):
    img_tag = ""
    if image_ref:
        img_tag = f'<p><img src="{image_ref}" alt="Question Image"/></p>'
    elif image_placeholder:
        img_tag = f"<p><em>[{image_placeholder}]</em></p>"

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


def create_mc_question(
    id,
    title,
    text,
    points,
    options,
    correct_index,
    image_ref=None,
    image_placeholder=None,
):
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

    template = create_item_header(id, title, points, image_ref, image_placeholder)
    return template.format(
        qt="multiple_choice_question",
        question_text=text,
        response_block=response_block,
        processing_block=processing_block,
    )


def create_tf_question(
    id, title, text, points, is_true, image_ref=None, image_placeholder=None
):
    return create_mc_question(
        id,
        title,
        text,
        points,
        ["True", "False"],
        0 if is_true else 1,
        image_ref,
        image_placeholder,
    )


def create_essay_question(
    id, title, text, points, image_ref=None, image_placeholder=None
):
    response_block = """<response_str ident="response1" rcardinality="Single">
            <render_fib>
              <response_label ident="answer1"/>
            </render_fib>
          </response_str>"""

    processing_block = """<respcondition continue="No">
            <conditionvar>
              <other/>
            </conditionvar>
          </respcondition>"""

    template = create_item_header(id, title, points, image_ref, image_placeholder)
    return template.format(
        qt="essay_question",
        question_text=text,
        response_block=response_block,
        processing_block=processing_block,
    )


def create_multiple_answers_question(
    id,
    title,
    text,
    points,
    options,
    correct_indices,
    image_ref=None,
    image_placeholder=None,
):
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
    # Create a condition for each option
    for i in range(len(options)):
        if i in correct_indices:
            conditions += f'<varequal respident="response1">opt_{i}</varequal>'
        else:
            conditions += (
                f'<not><varequal respident="response1">opt_{i}</varequal></not>'
            )

    processing_block = f"""<respcondition continue="No">
            <conditionvar>
              <and>
                {conditions}
              </and>
            </conditionvar>
            <setvar action="Set" varname="SCORE">{points}</setvar>
          </respcondition>"""

    template = create_item_header(id, title, points, image_ref, image_placeholder)
    return template.format(
        qt="multiple_answers_question",
        question_text=text,
        response_block=response_block,
        processing_block=processing_block,
    )


def generate_pdf_preview(questions, filename, quiz_title, image_map=None):
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    y_position = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y_position, quiz_title)
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
        image_ref = q.get("image_ref")
        image_placeholder = q.get("image_placeholder")

        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y_position, f"{i+1}. {q_title} ({q_points} points)")
        y_position -= 20

        # Draw Image or Placeholder
        if image_ref and image_map and image_ref in image_map:
            try:
                img_path = image_map[image_ref]
                img = ImageReader(img_path)
                iw, ih = img.getSize()
                aspect = ih / float(iw)
                display_width = 400
                display_height = display_width * aspect

                if y_position - display_height < 50:
                    c.showPage()
                    y_position = height - 50

                c.drawImage(
                    img_path,
                    50,
                    y_position - display_height,
                    width=display_width,
                    height=display_height,
                )
                y_position -= display_height + 20
            except Exception as e:
                print(f"Error drawing image {image_ref}: {e}")

        elif image_placeholder:
            if y_position - 60 < 50:
                c.showPage()
                y_position = height - 50

            c.setStrokeColorRGB(0.5, 0.5, 0.5)
            c.rect(50, y_position - 50, 400, 50, fill=0)

            # Simple text wrap for placeholder
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(60, y_position - 20, "IMAGE PLACEHOLDER:")
            c.drawString(
                60, y_position - 35, image_placeholder[:80]
            )  # Truncate for simplicity
            y_position -= 70

        c.setFont("Helvetica", 10)

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

        if q_type == "mc":
            options = q.get("options", [])
            correct_idx = q.get("correct_index", -1)
            for idx, opt in enumerate(options):
                prefix = "[x]" if idx == correct_idx else "[ ]"
                c.drawString(70, y_position, f"{prefix} {opt}")
                y_position -= 15
        elif q_type == "tf":
            is_true = q.get("is_true", False)
            c.drawString(70, y_position, "[x] True" if is_true else "[ ] True")
            y_position -= 15
            c.drawString(70, y_position, "[ ] False" if is_true else "[x] False")
            y_position -= 15

        y_position -= 20

    c.save()


def create_qti_package(questions, used_images, config):
    """
    Generates the QTI zip package for Canvas.
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    assessment_id = uuid.uuid4().hex
    manifest_id = uuid.uuid4().hex

    # Build XML for each question
    question_xml_parts = []
    for i, q in enumerate(questions):
        q_id = f"q{i+1}"
        image_ref = q.get("image_ref")
        image_placeholder = q.get("image_placeholder")

        q_type = q.get("type", "mc")

        if q_type == "mc":
            question_xml_parts.append(
                create_mc_question(
                    q_id,
                    q.get("title", "Question"),
                    q.get("text", ""),
                    q.get("points", 5),
                    q.get("options", []),
                    q.get("correct_index", 0),
                    image_ref,
                    image_placeholder,
                )
            )
        elif q_type == "tf":
            question_xml_parts.append(
                create_tf_question(
                    q_id,
                    q.get("title", "Question"),
                    q.get("text", ""),
                    q.get("points", 5),
                    q.get("is_true", True),
                    image_ref,
                    image_placeholder,
                )
            )
        elif q_type == "essay":
            question_xml_parts.append(
                create_essay_question(
                    q_id,
                    q.get("title", "Question"),
                    q.get("text", ""),
                    q.get("points", 5),
                    image_ref,
                    image_placeholder,
                )
            )
        elif q_type == "ma":
            correct_indices = q.get("correct_indices", [])
            if not correct_indices and "correct_index" in q:
                correct_indices = [q["correct_index"]]
            question_xml_parts.append(
                create_multiple_answers_question(
                    q_id,
                    q.get("title", "Question"),
                    q.get("text", ""),
                    q.get("points", 5),
                    q.get("options", []),
                    correct_indices,
                    image_ref,
                    image_placeholder,
                )
            )
        else:
            print(f"Warning: Unknown question type {q_type}, defaulting to MC")
            question_xml_parts.append(
                create_mc_question(
                    q_id,
                    q.get("title", "Question"),
                    q.get("text", ""),
                    q.get("points", 5),
                    q.get("options", []),
                    q.get("correct_index", 0),
                    image_ref,
                    image_placeholder,
                )
            )

    # Assemble the full assessment XML
    quiz_content = ASSESSMENT_HEADER.format(
        assessment_id=assessment_id, title=config["generation"]["quiz_title"]
    )
    quiz_content += "\n".join(question_xml_parts)
    quiz_content += ASSESSMENT_FOOTER

    # Build the manifest
    manifest_content = MANIFEST_TEMPLATE_START.format(
        manifest_id=manifest_id,
        assessment_id=assessment_id,
        assessment_filename=config["qti"]["assessment_filename"],
    )
    for _, img_name in used_images:
        manifest_content += f'\n      <file href="{img_name}"/>'
    manifest_content += MANIFEST_TEMPLATE_END

    # Write the zip file
    zip_filename = os.path.join(
        config["paths"]["quiz_output_dir"],
        config["qti"]["zip_filename_template"].format(timestamp=timestamp),
    )

    with zipfile.ZipFile(zip_filename, "w") as zipf:
        zipf.writestr(config["qti"]["manifest_name"], manifest_content)
        zipf.writestr(config["qti"]["assessment_filename"], quiz_content)
        for img_path, img_name in used_images:
            zipf.write(img_path, img_name)

    return zip_filename
