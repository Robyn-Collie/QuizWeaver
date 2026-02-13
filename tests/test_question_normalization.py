"""Tests for question normalization in agents.py and question_regenerator.py.

Covers BL-047 (short-answer normalization) and BL-048 (default points).
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from src.question_regenerator import normalize_question_data


class TestNormalizeQuestionData(unittest.TestCase):
    """Tests for normalize_question_data() in question_regenerator.py."""

    # --- BL-047: question_type mapping ---

    def test_short_answer_via_question_type(self):
        """Short answer question with question_type field gets type short_answer."""
        q = normalize_question_data({
            "text": "What is photosynthesis?",
            "question_type": "Short Answer",
            "correct_answer": "The process by which plants convert sunlight to energy",
        })
        assert q["type"] == "short_answer"
        assert "options" not in q
        assert q["correct_answer"] == "The process by which plants convert sunlight to energy"

    def test_multiple_choice_via_question_type(self):
        """Multiple choice via question_type field maps to mc."""
        q = normalize_question_data({
            "text": "What color is the sky?",
            "question_type": "Multiple Choice",
            "options": ["Red", "Blue", "Green"],
            "correct_index": 1,
        })
        assert q["type"] == "mc"

    def test_true_false_via_question_type(self):
        """True/false via question_type field maps to tf."""
        q = normalize_question_data({
            "text": "The earth is flat.",
            "question_type": "True/False",
        })
        assert q["type"] == "tf"

    def test_fill_in_blank_via_question_type(self):
        """Fill in the blank via question_type maps to fill_in_blank."""
        q = normalize_question_data({
            "text": "The capital of France is ___.",
            "question_type": "Fill in the Blank",
            "correct_answer": "Paris",
        })
        assert q["type"] == "fill_in_blank"

    def test_essay_via_question_type(self):
        """Essay via question_type maps to essay."""
        q = normalize_question_data({
            "text": "Discuss the causes of WWI.",
            "question_type": "Essay",
        })
        assert q["type"] == "essay"

    def test_ordering_via_question_type(self):
        """Ordering via question_type maps to ordering."""
        q = normalize_question_data({
            "text": "Order these events chronologically.",
            "question_type": "Ordering",
            "options": ["Event A", "Event B", "Event C"],
        })
        assert q["type"] == "ordering"

    def test_question_type_case_insensitive(self):
        """question_type mapping is case-insensitive."""
        q = normalize_question_data({
            "text": "Define osmosis.",
            "question_type": "  short answer  ",
        })
        assert q["type"] == "short_answer"

    def test_question_type_does_not_override_explicit_type(self):
        """If type is already set, question_type is ignored."""
        q = normalize_question_data({
            "text": "What?",
            "type": "mc",
            "question_type": "Short Answer",
            "options": ["A", "B"],
            "correct_index": 0,
        })
        assert q["type"] == "mc"

    def test_unknown_question_type_falls_through(self):
        """Unknown question_type value falls through to structural inference."""
        q = normalize_question_data({
            "text": "Something",
            "question_type": "Unknown Type XYZ",
            "options": ["A", "B"],
            "correct_index": 0,
        })
        # Falls through to structural inference: has options -> mc
        assert q["type"] == "mc"

    # --- BL-047: structural inference fallback (no options -> short_answer) ---

    def test_no_options_no_type_defaults_to_short_answer(self):
        """Question with text but no options/is_true defaults to short_answer, not mc."""
        q = normalize_question_data({
            "text": "Explain gravity.",
        })
        assert q["type"] == "short_answer"
        assert "options" not in q  # No synthetic options created

    def test_mc_inference_from_options(self):
        """Question with options but no type infers mc."""
        q = normalize_question_data({
            "text": "Pick one.",
            "options": ["A", "B", "C"],
            "correct_index": 0,
        })
        assert q["type"] == "mc"

    def test_ma_inference_from_correct_indices(self):
        """Question with correct_indices infers ma."""
        q = normalize_question_data({
            "text": "Select all that apply.",
            "options": ["A", "B", "C"],
            "correct_indices": [0, 2],
        })
        assert q["type"] == "ma"

    def test_tf_inference_from_is_true(self):
        """Question with is_true infers tf."""
        q = normalize_question_data({
            "text": "Water boils at 100C.",
            "is_true": True,
        })
        assert q["type"] == "tf"

    # --- BL-048: default points ---

    def test_default_points_added_when_missing(self):
        """Question with no points gets default of 1."""
        q = normalize_question_data({
            "text": "What?",
            "type": "mc",
            "options": ["A", "B"],
            "correct_index": 0,
        })
        assert q["points"] == 1

    def test_default_points_added_when_zero(self):
        """Question with 0 points gets default of 1."""
        q = normalize_question_data({
            "text": "What?",
            "type": "mc",
            "options": ["A", "B"],
            "correct_index": 0,
            "points": 0,
        })
        assert q["points"] == 1

    def test_existing_points_not_overwritten(self):
        """Question with existing points is not overwritten."""
        q = normalize_question_data({
            "text": "What?",
            "type": "mc",
            "options": ["A", "B"],
            "correct_index": 0,
            "points": 5,
        })
        assert q["points"] == 5

    # --- Text key normalization ---

    def test_question_text_alias(self):
        """question_text is mapped to text."""
        q = normalize_question_data({
            "question_text": "Define photosynthesis.",
            "type": "short_answer",
        })
        assert q["text"] == "Define photosynthesis."

    def test_answer_alias(self):
        """answer is mapped to correct_answer."""
        q = normalize_question_data({
            "text": "What?",
            "type": "short_answer",
            "answer": "Something",
        })
        assert q["correct_answer"] == "Something"


class TestGeneratorAgentNormalization(unittest.TestCase):
    """Tests for the normalizer inside GeneratorAgent.generate() in agents.py."""

    def _make_generator_agent(self):
        """Create a GeneratorAgent with a mock provider."""
        from src.agents import GeneratorAgent

        config = {
            "llm": {"provider": "mock"},
            "prompts": {},
        }
        agent = GeneratorAgent(config, provider=MagicMock())
        return agent

    def _generate_with_mock_response(self, agent, questions_json):
        """Run agent.generate() with a mocked LLM response."""
        agent.provider.generate.return_value = json.dumps(questions_json)
        result = agent.generate(
            context={
                "content_summary": "Test content",
                "question_count": len(questions_json),
            },
        )
        return result

    def test_short_answer_via_question_type_in_agent(self):
        """GeneratorAgent normalizer maps question_type Short Answer correctly."""
        agent = self._make_generator_agent()
        result = self._generate_with_mock_response(agent, [
            {
                "text": "What is mitosis?",
                "question_type": "Short Answer",
                "correct_answer": "Cell division process",
            }
        ])
        assert len(result) == 1
        assert result[0]["type"] == "short_answer"
        assert "options" not in result[0]
        assert result[0]["correct_answer"] == "Cell division process"

    def test_mc_still_works_in_agent(self):
        """GeneratorAgent normalizer still handles MC correctly."""
        agent = self._make_generator_agent()
        result = self._generate_with_mock_response(agent, [
            {
                "text": "What color?",
                "options": ["Red", "Blue"],
                "correct_index": 1,
            }
        ])
        assert len(result) == 1
        assert result[0]["type"] == "mc"

    def test_default_points_in_agent(self):
        """GeneratorAgent normalizer adds default points."""
        agent = self._make_generator_agent()
        result = self._generate_with_mock_response(agent, [
            {
                "text": "What?",
                "type": "mc",
                "options": ["A", "B"],
                "correct_index": 0,
            }
        ])
        assert result[0]["points"] == 1

    def test_existing_points_preserved_in_agent(self):
        """GeneratorAgent normalizer preserves existing points."""
        agent = self._make_generator_agent()
        result = self._generate_with_mock_response(agent, [
            {
                "text": "What?",
                "type": "mc",
                "options": ["A", "B"],
                "correct_index": 0,
                "points": 3,
            }
        ])
        assert result[0]["points"] == 3

    def test_no_synthetic_options_for_short_answer_in_agent(self):
        """GeneratorAgent does NOT create fake True/False options for short_answer."""
        agent = self._make_generator_agent()
        result = self._generate_with_mock_response(agent, [
            {
                "text": "Explain the water cycle.",
            }
        ])
        assert len(result) == 1
        assert result[0]["type"] == "short_answer"
        assert "options" not in result[0]

    def test_fill_in_blank_via_question_type_in_agent(self):
        """GeneratorAgent normalizer maps Fill in the Blank correctly."""
        agent = self._make_generator_agent()
        result = self._generate_with_mock_response(agent, [
            {
                "text": "The capital of France is ___.",
                "question_type": "Fill in the Blank",
                "correct_answer": "Paris",
            }
        ])
        assert result[0]["type"] == "fill_in_blank"


if __name__ == "__main__":
    unittest.main()
