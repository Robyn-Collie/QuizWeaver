"""
Edge case and boundary condition tests for QuizWeaver modules.

Covers: agents (load_prompt, get_qa_guidelines), mock_responses (fill_template_context),
llm_provider (get_provider factory), lesson_tracker (extract_topics), classroom
(create_class edge cases), and quiz_generator (generate_quiz edge cases).

Run with: python -m pytest tests/test_edge_cases.py -v
"""

import json
import os
import sys
import tempfile

import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents import get_qa_guidelines, load_prompt
from src.classroom import create_class
from src.database import Quiz
from src.lesson_tracker import KNOWN_TOPICS, extract_topics
from src.llm_provider import MockLLMProvider, get_provider
from src.mock_responses import SCIENCE_TOPICS, fill_template_context
from src.quiz_generator import generate_quiz

# ---------------------------------------------------------------------------
# Fixtures — db_session is provided by tests/conftest.py
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 1. TestLoadPrompt
# ---------------------------------------------------------------------------


class TestLoadPrompt:
    """Tests for src.agents.load_prompt utility function."""

    def test_load_prompt_existing_file(self):
        """Loading generator_prompt.txt should return a non-empty string."""
        # load_prompt uses a relative path ("prompts/<filename>"), so it must
        # be called from the project root.  Change there temporarily.
        original_cwd = os.getcwd()
        try:
            os.chdir(os.path.join(os.path.dirname(__file__), ".."))
            result = load_prompt("generator_prompt.txt")
            assert isinstance(result, str), "load_prompt should return a string"
            assert len(result) > 0, "generator_prompt.txt should not be empty"
            print("[PASS] load_prompt returns non-empty string for existing file")
        finally:
            os.chdir(original_cwd)

    def test_load_prompt_missing_file(self):
        """Loading a nonexistent prompt file should return an empty string."""
        original_cwd = os.getcwd()
        try:
            os.chdir(os.path.join(os.path.dirname(__file__), ".."))
            result = load_prompt("nonexistent_prompt.txt")
            assert result == "", "Missing file should return empty string"
            print("[PASS] load_prompt returns '' for missing file")
        finally:
            os.chdir(original_cwd)

    def test_load_prompt_empty_filename(self):
        """Loading with an empty filename should return an empty string or raise."""
        original_cwd = os.getcwd()
        try:
            os.chdir(os.path.join(os.path.dirname(__file__), ".."))
            try:
                result = load_prompt("")
                # On Windows, empty string causes FileNotFoundError -> returns ""
                assert result == "", "Empty filename should return empty string"
            except (IsADirectoryError, OSError):
                # On Linux/macOS, prompts/ + "" = prompts/ which is a directory
                pass
            print("[PASS] load_prompt handles empty filename")
        finally:
            os.chdir(original_cwd)

    def test_load_prompt_content_matches(self):
        """Content returned by load_prompt must match a direct file read."""
        original_cwd = os.getcwd()
        try:
            os.chdir(os.path.join(os.path.dirname(__file__), ".."))
            loaded = load_prompt("generator_prompt.txt")
            # Read the same file directly
            prompt_path = os.path.join("prompts", "generator_prompt.txt")
            with open(prompt_path) as f:
                direct = f.read()
            assert loaded == direct, "load_prompt content should match direct read"
            print("[PASS] load_prompt content matches direct file read")
        finally:
            os.chdir(original_cwd)


# ---------------------------------------------------------------------------
# 2. TestGetQaGuidelines
# ---------------------------------------------------------------------------


class TestGetQaGuidelines:
    """Tests for src.agents.get_qa_guidelines utility function."""

    def test_get_qa_guidelines_returns_string(self):
        """get_qa_guidelines should always return a string (even if file missing)."""
        original_cwd = os.getcwd()
        try:
            os.chdir(os.path.join(os.path.dirname(__file__), ".."))
            result = get_qa_guidelines()
            assert isinstance(result, str), "Should return a string"
            print("[PASS] get_qa_guidelines returns a string")
        finally:
            os.chdir(original_cwd)

    def test_get_qa_guidelines_no_crash_on_missing(self):
        """get_qa_guidelines must not raise when qa_guidelines.txt is absent."""
        # Run from a temp directory where qa_guidelines.txt definitely does not exist
        original_cwd = os.getcwd()
        tmp_dir = tempfile.mkdtemp()
        try:
            os.chdir(tmp_dir)
            result = get_qa_guidelines()
            assert isinstance(result, str), "Should return a string"
            assert result == "", "Should return empty string when file missing"
            print("[PASS] get_qa_guidelines does not crash on missing file")
        finally:
            os.chdir(original_cwd)
            try:
                os.rmdir(tmp_dir)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# 3. TestFillTemplateContext
# ---------------------------------------------------------------------------


class TestFillTemplateContext:
    """Tests for src.mock_responses.fill_template_context."""

    def test_fill_with_keywords(self):
        """Explicit keywords should replace {topic1} and {topic2} placeholders."""
        template = "{topic1} and {topic2}"
        result = fill_template_context(template, ["photosynthesis", "cells"])
        assert result == "photosynthesis and cells", f"Expected 'photosynthesis and cells', got '{result}'"
        print("[PASS] fill_template_context replaces placeholders with keywords")

    def test_fill_with_no_keywords(self):
        """When keywords is None, random topics should replace placeholders."""
        template = "{topic1} and {topic2} and {topic3}"
        result = fill_template_context(template, None)
        # All three placeholders should be replaced (no leftover braces)
        assert "{topic1}" not in result, "Placeholder {topic1} should be replaced"
        assert "{topic2}" not in result, "Placeholder {topic2} should be replaced"
        assert "{topic3}" not in result, "Placeholder {topic3} should be replaced"
        # Each replacement should be a valid SCIENCE_TOPICS entry
        parts = result.split(" and ")
        for part in parts:
            assert part in SCIENCE_TOPICS, f"'{part}' should be a valid SCIENCE_TOPICS entry"
        print("[PASS] fill_template_context fills with random topics when no keywords")

    def test_fill_no_placeholders(self):
        """Template without placeholders should remain unchanged."""
        template = "plain text with no placeholders"
        result = fill_template_context(template, ["photosynthesis", "cells"])
        assert result == template, "Text without placeholders should not change"
        print("[PASS] fill_template_context leaves plain text unchanged")

    def test_fill_single_keyword(self):
        """A single-element keyword list should fill {topic1} correctly."""
        template = "{topic1}"
        result = fill_template_context(template, ["mitosis"])
        assert result == "mitosis", f"Expected 'mitosis', got '{result}'"
        print("[PASS] fill_template_context handles single keyword list")


# ---------------------------------------------------------------------------
# 4. TestGetProviderFactory
# ---------------------------------------------------------------------------


class TestGetProviderFactory:
    """Tests for src.llm_provider.get_provider factory function."""

    def test_get_provider_mock(self):
        """Config with llm.provider='mock' should return a MockLLMProvider."""
        config = {"llm": {"provider": "mock"}}
        provider = get_provider(config)
        assert isinstance(provider, MockLLMProvider), f"Expected MockLLMProvider, got {type(provider).__name__}"
        print("[PASS] get_provider returns MockLLMProvider for provider='mock'")

    def test_get_provider_default_mock(self):
        """Config with no llm section should default to MockLLMProvider."""
        config = {}
        provider = get_provider(config)
        assert isinstance(provider, MockLLMProvider), f"Expected MockLLMProvider, got {type(provider).__name__}"
        print("[PASS] get_provider defaults to MockLLMProvider with empty config")

    def test_get_provider_unsupported(self):
        """Config with an unsupported provider name should raise ValueError."""
        config = {"llm": {"provider": "unsupported"}}
        with pytest.raises(ValueError, match="Unsupported provider"):
            get_provider(config)
        print("[PASS] get_provider raises ValueError for unsupported provider")

    def test_get_provider_gemini_no_key(self, monkeypatch):
        """Gemini provider in production mode without API key should raise ValueError."""
        # Ensure GEMINI_API_KEY is not set
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        config = {"llm": {"provider": "gemini", "mode": "production"}}
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            get_provider(config)
        print("[PASS] get_provider raises ValueError when GEMINI_API_KEY missing")


# ---------------------------------------------------------------------------
# 5. TestExtractTopicsEdgeCases
# ---------------------------------------------------------------------------


class TestExtractTopicsEdgeCases:
    """Tests for src.lesson_tracker.extract_topics edge cases."""

    def test_extract_topics_empty_string(self):
        """An empty string should return an empty list."""
        result = extract_topics("")
        assert result == [], f"Expected [], got {result}"
        print("[PASS] extract_topics returns [] for empty string")

    def test_extract_topics_long_text(self):
        """extract_topics should handle large text (10000+ chars) mentioning topics."""
        # Build a long text containing known topics
        filler = "This is filler text about general science. " * 200
        long_text = filler + " Photosynthesis is a key process. " + filler + " Mitosis occurs in cells."
        result = extract_topics(long_text)
        assert "photosynthesis" in result, "Should find 'photosynthesis'"
        assert "mitosis" in result, "Should find 'mitosis'"
        assert len(long_text) > 10000, "Test text should exceed 10000 chars"
        print("[PASS] extract_topics works with long text")

    def test_extract_topics_multi_word(self):
        """Multi-word topics like 'cellular respiration' should be matched."""
        text = "Today we studied cellular respiration and plate tectonics."
        result = extract_topics(text)
        assert "cellular respiration" in result, "Should find multi-word topic 'cellular respiration'"
        assert "plate tectonics" in result, "Should find multi-word topic 'plate tectonics'"
        print("[PASS] extract_topics handles multi-word topics")

    def test_extract_topics_all_topics(self):
        """Text containing every KNOWN_TOPIC should return all of them."""
        # Join all known topics into one text
        text = " ".join(KNOWN_TOPICS)
        result = extract_topics(text)
        for topic in KNOWN_TOPICS:
            assert topic in result, f"Should find topic '{topic}'"
        print("[PASS] extract_topics finds all KNOWN_TOPICS")


# ---------------------------------------------------------------------------
# 6. TestClassEdgeCases
# ---------------------------------------------------------------------------


class TestClassEdgeCases:
    """Tests for src.classroom.create_class with edge-case inputs."""

    def test_create_class_empty_name(self, db_session):
        """Creating a class with an empty name should succeed."""
        session, db_path = db_session
        cls = create_class(session, name="")
        assert cls is not None, "Should return a Class object"
        assert cls.id is not None, "Class should have an assigned ID"
        assert cls.name == "", "Name should be empty string"
        print("[PASS] create_class allows empty name")

    def test_create_class_long_name(self, db_session):
        """Creating a class with a 500-character name should store correctly."""
        session, db_path = db_session
        long_name = "A" * 500
        cls = create_class(session, name=long_name)
        assert cls is not None, "Should return a Class object"
        assert cls.name == long_name, "Full 500-char name should be stored"
        assert len(cls.name) == 500, "Name length should be 500"
        print("[PASS] create_class stores 500-char name correctly")

    def test_create_class_special_chars(self, db_session):
        """Creating a class with quotes and backslashes should store correctly."""
        session, db_path = db_session
        special_name = 'Block "A" \\ Period 1\'s Class'
        cls = create_class(session, name=special_name)
        assert cls is not None, "Should return a Class object"
        assert cls.name == special_name, f"Name should preserve special chars, got: {cls.name}"
        print("[PASS] create_class stores names with quotes and backslashes")


# ---------------------------------------------------------------------------
# 7. TestQuizGeneratorEdgeCases
# ---------------------------------------------------------------------------


class TestQuizGeneratorEdgeCases:
    """Tests for src.quiz_generator.generate_quiz edge cases."""

    def _make_config(self, db_path):
        """Build a minimal mock config dict for generate_quiz."""
        return {
            "llm": {"provider": "mock"},
            "paths": {"database_file": db_path},
            "generation": {
                "quiz_title": "Edge Case Quiz",
                "default_grade_level": "7th Grade Science",
                "sol_standards": [],
                "target_image_ratio": 0.0,
                "generate_ai_images": False,
                "interactive_review": False,
            },
        }

    def test_generate_quiz_zero_questions(self, db_session):
        """generate_quiz with num_questions=0 should still return a Quiz (mock produces 3-5)."""
        session, db_path = db_session
        config = self._make_config(db_path)
        cls = create_class(session, name="Zero Questions Class", grade_level="7th Grade")
        quiz = generate_quiz(session, cls.id, config, num_questions=0)
        # MockLLMProvider always generates 3-5 questions regardless of request
        assert quiz is not None, "Should return a Quiz object even with num_questions=0"
        assert isinstance(quiz, Quiz), f"Expected Quiz, got {type(quiz).__name__}"
        assert quiz.status == "generated", "Status should be 'generated'"
        print("[PASS] generate_quiz handles num_questions=0")

    def test_generate_quiz_class_with_null_grade(self, db_session):
        """Class with grade_level=None should fall back to config default."""
        session, db_path = db_session
        config = self._make_config(db_path)
        cls = create_class(session, name="No Grade Class", grade_level=None)
        quiz = generate_quiz(session, cls.id, config)
        assert quiz is not None, "Should return a Quiz"
        # grade should fall back to config default_grade_level
        profile = quiz.style_profile
        if isinstance(profile, str):
            profile = json.loads(profile)
        assert profile is not None, "style_profile should not be None"
        profile_str = json.dumps(profile) if isinstance(profile, dict) else str(profile)
        assert "7th Grade Science" in profile_str, (
            f"Expected config default '7th Grade Science' in profile, got: {profile_str}"
        )
        print("[PASS] generate_quiz falls back to config grade when class grade is None")

    def test_generate_quiz_empty_sol_standards(self, db_session):
        """generate_quiz with sol_standards=[] should create a quiz successfully."""
        session, db_path = db_session
        config = self._make_config(db_path)
        cls = create_class(session, name="No SOL Class", grade_level="8th Grade")
        quiz = generate_quiz(session, cls.id, config, sol_standards=[])
        assert quiz is not None, "Should return a Quiz"
        assert isinstance(quiz, Quiz), f"Expected Quiz, got {type(quiz).__name__}"
        assert len(quiz.questions) > 0, "Should have at least one question"
        print("[PASS] generate_quiz handles empty sol_standards list")
