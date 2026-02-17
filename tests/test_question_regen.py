"""Tests for src/question_regenerator.py — single question regeneration.

Covers normalize_question_data() edge cases not in test_question_normalization.py,
and regenerate_question() with mock providers, error handling, and provider override.
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.database import Class, Question, Quiz, get_engine, get_session, init_db
from src.question_regenerator import normalize_question_data, regenerate_question

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def regen_db():
    """Provide a temp DB with ORM tables and a quiz + question."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    engine = get_engine(tmp.name)
    init_db(engine)
    session = get_session(engine)

    cls = Class(
        name="Test Class",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps(["SOL 7.1"]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()

    quiz = Quiz(
        title="Test Quiz",
        class_id=cls.id,
        status="generated",
        style_profile=json.dumps({"grade_level": "7th Grade", "provider": "mock"}),
    )
    session.add(quiz)
    session.commit()

    question = Question(
        quiz_id=quiz.id,
        question_type="mc",
        title="Q1",
        text="What is photosynthesis?",
        points=5.0,
        data=json.dumps(
            {
                "type": "mc",
                "text": "What is photosynthesis?",
                "options": ["A process", "A disease", "A planet", "A tool"],
                "correct_index": 0,
                "image_ref": "photo_001.png",
                "cognitive_level": "Remember",
            }
        ),
    )
    session.add(question)
    session.commit()

    yield session, tmp.name, quiz, question
    session.close()
    engine.dispose()
    try:
        os.remove(tmp.name)
    except OSError:
        pass


@pytest.fixture
def mock_config():
    """Config dict for regeneration tests."""
    return {
        "llm": {"provider": "mock"},
        "paths": {},
    }


# ---------------------------------------------------------------------------
# normalize_question_data — additional edge cases
# ---------------------------------------------------------------------------


def test_normalize_dict_options_to_list():
    """Dict-style options {A: ..., B: ...} are converted to a list."""
    q = normalize_question_data(
        {
            "text": "Pick one",
            "type": "mc",
            "options": {"A": "Apple", "B": "Banana", "C": "Cherry"},
            "correct_answer": "B",
        }
    )
    assert isinstance(q["options"], list)
    assert q["options"] == ["Apple", "Banana", "Cherry"]
    assert q["correct_index"] == 1


def test_normalize_correct_answer_letter_to_index():
    """Single letter correct_answer (e.g., 'C') is mapped to correct_index."""
    q = normalize_question_data(
        {
            "text": "Pick one",
            "type": "mc",
            "options": ["Red", "Green", "Blue"],
            "correct_answer": "C",
        }
    )
    assert q["correct_index"] == 2


def test_normalize_correct_answer_text_to_index():
    """Correct answer matching option text is mapped to correct_index."""
    q = normalize_question_data(
        {
            "text": "Pick one",
            "type": "mc",
            "options": ["Red", "Green", "Blue"],
            "correct_answer": "Green",
        }
    )
    assert q["correct_index"] == 1


def test_normalize_stem_alias():
    """'stem' key is mapped to 'text'."""
    q = normalize_question_data({"stem": "What is 2+2?", "type": "short_answer"})
    assert q["text"] == "What is 2+2?"


def test_normalize_prompt_alias():
    """'prompt' key is mapped to 'text'."""
    q = normalize_question_data({"prompt": "Explain gravity.", "type": "essay"})
    assert q["text"] == "Explain gravity."


def test_normalize_body_alias():
    """'body' key is mapped to 'text'."""
    q = normalize_question_data({"body": "Describe the cell.", "type": "short_answer"})
    assert q["text"] == "Describe the cell."


def test_normalize_question_title_alias():
    """'question_title' is mapped to 'title'."""
    q = normalize_question_data(
        {"text": "What?", "question_title": "Biology Q1", "type": "mc", "options": ["A"], "correct_index": 0}
    )
    assert q["title"] == "Biology Q1"


def test_normalize_stimulus_type():
    """'stimulus/passage' maps to 'stimulus'."""
    q = normalize_question_data({"text": "Read the passage.", "question_type": "Stimulus/Passage"})
    assert q["type"] == "stimulus"


def test_normalize_matching_type():
    """'Matching' maps to 'matching'."""
    q = normalize_question_data({"text": "Match items.", "question_type": "Matching"})
    assert q["type"] == "matching"


def test_normalize_select_all_type():
    """'Select All That Apply' maps to 'ma'."""
    q = normalize_question_data(
        {
            "text": "Select all.",
            "question_type": "Select All That Apply",
            "options": ["A", "B"],
            "correct_indices": [0, 1],
        }
    )
    assert q["type"] == "ma"


# ---------------------------------------------------------------------------
# regenerate_question — success path
# ---------------------------------------------------------------------------


@patch("src.question_regenerator.get_provider")
def test_regenerate_question_success(mock_get_provider, regen_db, mock_config):
    """Successful regeneration updates the question text and data."""
    session, db_path, quiz, question = regen_db

    new_q = {
        "text": "What is cellular respiration?",
        "type": "mc",
        "options": ["Energy process", "Plant growth", "Water cycle", "Light reaction"],
        "correct_index": 0,
        "points": 5,
    }
    mock_provider = MagicMock()
    mock_provider.generate.return_value = json.dumps(new_q)
    mock_get_provider.return_value = mock_provider

    result = regenerate_question(session, question.id, "Make it harder", mock_config)

    assert result is not None
    assert result.text == "What is cellular respiration?"
    assert result.question_type == "mc"
    # Old cognitive fields should be preserved
    data = result.data if isinstance(result.data, dict) else json.loads(result.data)
    assert data.get("image_ref") == "photo_001.png"
    assert data.get("cognitive_level") == "Remember"


@patch("src.question_regenerator.get_provider")
def test_regenerate_question_not_found(mock_get_provider, regen_db, mock_config):
    """Returns None when question_id does not exist."""
    session, _, _, _ = regen_db
    result = regenerate_question(session, 9999, "notes", mock_config)
    assert result is None


@patch("src.question_regenerator.get_provider")
def test_regenerate_question_llm_failure(mock_get_provider, regen_db, mock_config):
    """Returns None when the LLM call raises an exception."""
    session, _, _, question = regen_db
    mock_provider = MagicMock()
    mock_provider.generate.side_effect = Exception("API timeout")
    mock_get_provider.return_value = mock_provider

    result = regenerate_question(session, question.id, "", mock_config)
    assert result is None


@patch("src.question_regenerator.get_provider")
def test_regenerate_question_invalid_json(mock_get_provider, regen_db, mock_config):
    """Returns None when LLM returns invalid JSON."""
    session, _, _, question = regen_db
    mock_provider = MagicMock()
    mock_provider.generate.return_value = "This is not JSON at all"
    mock_get_provider.return_value = mock_provider

    result = regenerate_question(session, question.id, "", mock_config)
    assert result is None


@patch("src.question_regenerator.get_provider")
def test_regenerate_question_array_response(mock_get_provider, regen_db, mock_config):
    """Handles LLM returning a JSON array by using the first element."""
    session, _, _, question = regen_db

    new_q = [
        {
            "text": "What is osmosis?",
            "type": "short_answer",
            "correct_answer": "Diffusion of water",
            "points": 2,
        }
    ]
    mock_provider = MagicMock()
    mock_provider.generate.return_value = json.dumps(new_q)
    mock_get_provider.return_value = mock_provider

    result = regenerate_question(session, question.id, "", mock_config)
    assert result is not None
    assert result.text == "What is osmosis?"
    assert result.question_type == "short_answer"


@patch("src.question_regenerator.get_provider")
def test_regenerate_question_empty_array(mock_get_provider, regen_db, mock_config):
    """Returns None when LLM returns an empty JSON array."""
    session, _, _, question = regen_db
    mock_provider = MagicMock()
    mock_provider.generate.return_value = "[]"
    mock_get_provider.return_value = mock_provider

    result = regenerate_question(session, question.id, "", mock_config)
    assert result is None


@patch("src.question_regenerator.get_provider")
def test_regenerate_strips_markdown_code_blocks(mock_get_provider, regen_db, mock_config):
    """Markdown code block wrappers are stripped before JSON parsing."""
    session, _, _, question = regen_db

    wrapped = '```json\n{"text": "What is gravity?", "type": "short_answer", "points": 1}\n```'
    mock_provider = MagicMock()
    mock_provider.generate.return_value = wrapped
    mock_get_provider.return_value = mock_provider

    result = regenerate_question(session, question.id, "", mock_config)
    assert result is not None
    assert result.text == "What is gravity?"


@patch("src.question_regenerator.get_provider")
def test_regenerate_uses_quiz_provider(mock_get_provider, regen_db, mock_config):
    """When quiz style_profile has a provider, it overrides config default."""
    session, _, quiz, question = regen_db

    # Set quiz provider to gemini (non-mock)
    quiz.style_profile = json.dumps({"grade_level": "7th Grade", "provider": "gemini"})
    session.commit()

    new_q = {"text": "New Q", "type": "mc", "options": ["A", "B"], "correct_index": 0}
    mock_provider = MagicMock()
    mock_provider.generate.return_value = json.dumps(new_q)
    mock_get_provider.return_value = mock_provider

    regenerate_question(session, question.id, "", mock_config)

    # Verify get_provider was called with gemini override
    call_args = mock_get_provider.call_args
    called_config = call_args[0][0]
    assert called_config["llm"]["provider"] == "gemini"
