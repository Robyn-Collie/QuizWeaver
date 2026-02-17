"""Tests for src/review.py — interactive quiz review flow.

Covers print_summary() output formatting, interactive_review() accept/reject
flow, image regeneration, and input handling.
"""

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# print_summary tests
# ---------------------------------------------------------------------------


def test_print_summary_basic_output(capsys):
    """print_summary displays question text and options."""
    from src.review import print_summary

    questions = [
        {
            "title": "Biology Q1",
            "text": "What is photosynthesis?",
            "options": ["Energy from sun", "Energy from food"],
            "correct_index": 0,
        }
    ]
    print_summary(questions, [])

    output = capsys.readouterr().out
    assert "Biology Q1" in output
    assert "What is photosynthesis?" in output
    assert "A. Energy from sun" in output
    assert "B. Energy from food" in output
    assert "Answer: A" in output


def test_print_summary_correct_answer_text(capsys):
    """print_summary shows correct_answer when present instead of correct_index."""
    from src.review import print_summary

    questions = [
        {
            "text": "Is the sky blue?",
            "correct_answer": "True",
        }
    ]
    print_summary(questions, [])

    output = capsys.readouterr().out
    assert "Answer: True" in output


def test_print_summary_image_ref_display(capsys):
    """print_summary shows image reference when available."""
    from src.review import print_summary

    questions = [
        {
            "text": "Identify the cell.",
            "image_ref": "cell_diagram.png",
        }
    ]
    print_summary(questions, [])

    output = capsys.readouterr().out
    assert "Image: cell_diagram.png" in output


def test_print_summary_placeholder_display(capsys):
    """print_summary shows 'Placeholder' for image_placeholder."""
    from src.review import print_summary

    questions = [
        {
            "text": "Label the diagram.",
            "image_placeholder": True,
        }
    ]
    print_summary(questions, [])

    output = capsys.readouterr().out
    assert "Placeholder" in output


def test_print_summary_no_image(capsys):
    """print_summary shows 'No Image' when no image data."""
    from src.review import print_summary

    questions = [{"text": "Simple question."}]
    print_summary(questions, [])

    output = capsys.readouterr().out
    assert "No Image" in output


def test_print_summary_auto_title(capsys):
    """When no title, auto-generates 'Question N'."""
    from src.review import print_summary

    questions = [{"text": "No title here."}]
    print_summary(questions, [])

    output = capsys.readouterr().out
    assert "Question 1" in output


# ---------------------------------------------------------------------------
# interactive_review tests
# ---------------------------------------------------------------------------


@patch("src.review.generate_pdf_preview")
@patch("builtins.input", return_value="A")
def test_interactive_review_accept(mock_input, mock_pdf, capsys):
    """Entering 'A' accepts the quiz and returns True."""
    from src.review import interactive_review

    questions = [{"text": "Q1", "options": ["A", "B"], "correct_index": 0}]
    used_images = []
    config = {}

    result = interactive_review(questions, used_images, config, MagicMock())
    assert result is True


@patch("src.review.generate_pdf_preview")
@patch("builtins.input", return_value="R")
def test_interactive_review_reject(mock_input, mock_pdf, capsys):
    """Entering 'R' rejects the quiz and returns False."""
    from src.review import interactive_review

    questions = [{"text": "Q1"}]
    used_images = []

    result = interactive_review(questions, used_images, {}, MagicMock())
    assert result is False


@patch("src.review.generate_pdf_preview")
@patch("builtins.input", side_effect=["G 1", "A"])
def test_interactive_review_regenerate_image(mock_input, mock_pdf, capsys):
    """'G 1' triggers image regeneration callback, then 'A' accepts."""
    from src.review import interactive_review

    questions = [{"text": "Q1", "image_placeholder": True}]
    used_images = []

    callback = MagicMock(return_value="/tmp/new_image.png")
    result = interactive_review(questions, used_images, {}, callback)

    assert result is True
    callback.assert_called_once_with(questions[0])
    assert questions[0].get("image_ref") == "new_image.png"
    assert "image_placeholder" not in questions[0]


@patch("src.review.generate_pdf_preview")
@patch("builtins.input", side_effect=["G 1", "A"])
def test_interactive_review_regen_failure(mock_input, mock_pdf, capsys):
    """When image regeneration fails (returns None), shows failure message."""
    from src.review import interactive_review

    questions = [{"text": "Q1"}]
    used_images = []

    callback = MagicMock(return_value=None)
    result = interactive_review(questions, used_images, {}, callback)

    assert result is True
    output = capsys.readouterr().out
    assert "Image generation failed" in output


@patch("src.review.generate_pdf_preview")
@patch("builtins.input", side_effect=["G", "A"])
def test_interactive_review_regen_missing_number(mock_input, mock_pdf, capsys):
    """'G' without a number shows an error prompt."""
    from src.review import interactive_review

    questions = [{"text": "Q1"}]
    result = interactive_review(questions, [], {}, MagicMock())

    assert result is True
    output = capsys.readouterr().out
    assert "Specify question number" in output


@patch("src.review.generate_pdf_preview")
@patch("builtins.input", side_effect=["G 99", "A"])
def test_interactive_review_regen_invalid_number(mock_input, mock_pdf, capsys):
    """'G 99' with out-of-range index shows invalid message."""
    from src.review import interactive_review

    questions = [{"text": "Q1"}]
    result = interactive_review(questions, [], {}, MagicMock())

    assert result is True
    output = capsys.readouterr().out
    assert "Invalid question number" in output


@patch("src.review.generate_pdf_preview")
@patch("builtins.input", side_effect=["X", "A"])
def test_interactive_review_unknown_command(mock_input, mock_pdf, capsys):
    """Unknown input shows 'Unknown command' and loops."""
    from src.review import interactive_review

    questions = [{"text": "Q1"}]
    result = interactive_review(questions, [], {}, MagicMock())

    assert result is True
    output = capsys.readouterr().out
    assert "Unknown command" in output


@patch("src.review.generate_pdf_preview", side_effect=Exception("PDF error"))
@patch("builtins.input", return_value="A")
def test_interactive_review_pdf_failure_continues(mock_input, mock_pdf, capsys):
    """When PDF generation fails, review continues with a warning."""
    from src.review import interactive_review

    questions = [{"text": "Q1"}]
    result = interactive_review(questions, [], {}, MagicMock())

    assert result is True
    output = capsys.readouterr().out
    assert "Could not generate preview PDF" in output
