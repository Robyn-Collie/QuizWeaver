"""
Tests for the structured critic architecture introduced in the Critic Agent Overhaul.

Covers:
- _parse_critic_response() structured JSON parsing
- _parse_critic_response() legacy fallback
- _build_critic_config() provider separation
- _extract_teacher_config()
- Orchestrator selective regeneration (accumulator pattern)
- Pre-validation integration in the pipeline
"""

import json
from unittest.mock import MagicMock, patch

from src.agents import (
    Orchestrator,
    _build_critic_config,
    _extract_teacher_config,
    _parse_critic_response,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_QUESTION_TEMPLATES = {
    "mc": lambda i: {
        "type": "mc",
        "text": f"Question {i}?",
        "options": ["A", "B", "C", "D"],
        "correct_index": 0,
        "points": 1,
    },
    "tf": lambda i: {
        "type": "tf",
        "text": f"Statement {i} is true.",
        "is_true": True,
        "points": 1,
    },
    "short_answer": lambda i: {
        "type": "short_answer",
        "text": f"Explain concept {i}.",
        "expected_answer": "Expected answer.",
        "points": 1,
    },
}


def _valid_q(i=0, qtype="mc"):
    """Return a structurally valid question dict."""
    factory = _QUESTION_TEMPLATES.get(qtype)
    if factory:
        return factory(i)
    return {"type": qtype, "text": f"Q {i}?", "points": 1}


def _structured_response(verdicts):
    """Build a structured JSON critic response string."""
    return json.dumps({"questions": verdicts, "overall_notes": "Test review."})


def _all_pass(n):
    return [{"index": i, "verdict": "PASS", "issues": [], "fact_check": "PASS"} for i in range(n)]


def _all_fail(n, issue="Bad question"):
    return [{"index": i, "verdict": "FAIL", "issues": [issue], "fact_check": "PASS"} for i in range(n)]


def _mixed(n_pass, n_fail):
    verdicts = []
    for i in range(n_pass):
        verdicts.append({"index": i, "verdict": "PASS", "issues": [], "fact_check": "PASS"})
    for i in range(n_fail):
        verdicts.append({"index": n_pass + i, "verdict": "FAIL", "issues": ["Rejected"], "fact_check": "PASS"})
    return verdicts


# ---------------------------------------------------------------------------
# _parse_critic_response tests
# ---------------------------------------------------------------------------


class TestParseCriticResponse:
    def test_all_pass_structured(self):
        resp = _structured_response(_all_pass(5))
        result = _parse_critic_response(resp, 5)
        assert result["status"] == "APPROVED"
        assert result["passed_indices"] == [0, 1, 2, 3, 4]
        assert result["failed_indices"] == []
        assert result["feedback"] is None

    def test_all_fail_structured(self):
        resp = _structured_response(_all_fail(3))
        result = _parse_critic_response(resp, 3)
        assert result["status"] == "REJECTED"
        assert result["passed_indices"] == []
        assert result["failed_indices"] == [0, 1, 2]
        assert result["feedback"] is not None

    def test_mixed_verdicts(self):
        resp = _structured_response(_mixed(2, 1))
        result = _parse_critic_response(resp, 3)
        assert result["status"] == "REJECTED"
        assert result["passed_indices"] == [0, 1]
        assert result["failed_indices"] == [2]

    def test_fact_check_warn_in_feedback(self):
        verdicts = [
            {
                "index": 0,
                "verdict": "FAIL",
                "issues": [],
                "fact_check": "WARN",
                "fact_check_notes": "Answer may be incorrect",
            },
        ]
        resp = _structured_response(verdicts)
        result = _parse_critic_response(resp, 1)
        assert "fact-check WARN" in result["feedback"]
        assert "Answer may be incorrect" in result["feedback"]

    def test_fact_check_fail_in_feedback(self):
        verdicts = [
            {
                "index": 0,
                "verdict": "FAIL",
                "issues": ["Wrong answer"],
                "fact_check": "FAIL",
                "fact_check_notes": "Incorrect fact",
            },
        ]
        resp = _structured_response(verdicts)
        result = _parse_critic_response(resp, 1)
        assert "fact-check FAIL" in result["feedback"]

    def test_markdown_fenced_json(self):
        inner = json.dumps({"questions": _all_pass(2), "overall_notes": ""})
        resp = f"```json\n{inner}\n```"
        result = _parse_critic_response(resp, 2)
        assert result["status"] == "APPROVED"
        assert len(result["passed_indices"]) == 2

    def test_json_with_preamble(self):
        """JSON embedded in surrounding text."""
        inner = json.dumps({"questions": _all_pass(1), "overall_notes": "OK"})
        resp = f"Here is my review:\n{inner}\nEnd of review."
        result = _parse_critic_response(resp, 1)
        assert result["status"] == "APPROVED"

    def test_legacy_approved_text(self):
        result = _parse_critic_response("APPROVED. Everything looks good.", 3)
        assert result["status"] == "APPROVED"
        assert result["passed_indices"] == [0, 1, 2]

    def test_legacy_rejected_text(self):
        result = _parse_critic_response("The questions have issues. Please revise.", 3)
        assert result["status"] == "REJECTED"
        assert result["failed_indices"] == [0, 1, 2]

    def test_empty_verdicts_list(self):
        resp = json.dumps({"questions": [], "overall_notes": "Nothing to review."})
        result = _parse_critic_response(resp, 0)
        assert result["status"] == "APPROVED"
        assert result["passed_indices"] == []
        assert result["failed_indices"] == []

    def test_verdict_case_insensitive(self):
        verdicts = [{"index": 0, "verdict": "pass", "issues": [], "fact_check": "PASS"}]
        resp = _structured_response(verdicts)
        result = _parse_critic_response(resp, 1)
        assert result["status"] == "APPROVED"

    def test_overall_notes_preserved(self):
        resp = json.dumps({"questions": _all_pass(1), "overall_notes": "Good alignment."})
        result = _parse_critic_response(resp, 1)
        assert result["overall_notes"] == "Good alignment."


# ---------------------------------------------------------------------------
# _build_critic_config tests
# ---------------------------------------------------------------------------


class TestBuildCriticConfig:
    def test_no_critic_section_returns_same(self):
        config = {"llm": {"provider": "mock"}}
        result = _build_critic_config(config)
        assert result is config

    def test_empty_critic_section_returns_same(self):
        config = {"llm": {"provider": "mock", "critic": {}}}
        result = _build_critic_config(config)
        assert result is config

    def test_null_provider_returns_same(self):
        config = {"llm": {"provider": "mock", "critic": {"provider": None}}}
        result = _build_critic_config(config)
        assert result is config

    def test_separate_provider(self):
        config = {"llm": {"provider": "mock", "critic": {"provider": "anthropic"}}}
        result = _build_critic_config(config)
        assert result is not config
        assert result["llm"]["provider"] == "anthropic"

    def test_separate_provider_with_model(self):
        config = {
            "llm": {
                "provider": "mock",
                "critic": {"provider": "gemini", "model_name": "gemini-2.5-flash"},
            }
        }
        result = _build_critic_config(config)
        assert result["llm"]["provider"] == "gemini"
        assert result["llm"]["model"] == "gemini-2.5-flash"

    def test_original_config_unchanged(self):
        config = {"llm": {"provider": "mock", "critic": {"provider": "anthropic"}}}
        _build_critic_config(config)
        assert config["llm"]["provider"] == "mock"


# ---------------------------------------------------------------------------
# _extract_teacher_config tests
# ---------------------------------------------------------------------------


class TestExtractTeacherConfig:
    def test_no_distribution_returns_none(self):
        assert _extract_teacher_config({}) is None

    def test_distribution_with_types(self):
        context = {
            "cognitive_distribution": {
                "remember": {"count": 2, "types": ["mc", "tf"]},
                "apply": {"count": 1, "types": ["short_answer"]},
            }
        }
        result = _extract_teacher_config(context)
        assert result is not None
        assert set(result["allowed_types"]) == {"mc", "tf", "short_answer"}

    def test_distribution_without_types(self):
        context = {
            "cognitive_distribution": {
                "remember": {"count": 2},
            }
        }
        result = _extract_teacher_config(context)
        assert result is None

    def test_non_dict_entries_ignored(self):
        context = {
            "cognitive_distribution": {
                "remember": "just a string",
                "apply": {"count": 1, "types": ["mc"]},
            }
        }
        result = _extract_teacher_config(context)
        assert result == {"allowed_types": ["mc"]}


# ---------------------------------------------------------------------------
# Orchestrator selective regeneration
# ---------------------------------------------------------------------------


class TestSelectiveRegeneration:
    """Test that the Orchestrator accumulates approved questions across attempts."""

    def _make_config(self):
        return {
            "llm": {"provider": "mock"},
            "agent_loop": {"max_retries": 3},
        }

    @patch("src.agents.get_provider")
    def test_all_approved_first_try(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_get_provider.return_value = mock_provider

        questions = [_valid_q(i) for i in range(5)]
        mock_provider.generate.side_effect = [
            json.dumps(questions),  # generator
            _structured_response(_all_pass(5)),  # critic
        ]

        orch = Orchestrator(self._make_config(), web_mode=True)
        result_qs, metadata = orch.run({"num_questions": 5, "content_summary": "test"})
        assert len(result_qs) == 5
        assert orch.last_metrics.generator_calls == 1
        assert orch.last_metrics.critic_calls == 1

    @patch("src.agents.get_provider")
    def test_partial_approval_triggers_regen(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_get_provider.return_value = mock_provider

        qs_attempt1 = [_valid_q(i) for i in range(5)]
        qs_attempt2 = [_valid_q(i + 5) for i in range(2)]

        mock_provider.generate.side_effect = [
            json.dumps(qs_attempt1),  # gen attempt 1
            _structured_response(_mixed(3, 2)),  # critic: 3 pass, 2 fail
            json.dumps(qs_attempt2),  # gen attempt 2 (needs 2 more)
            _structured_response(_all_pass(2)),  # critic: 2 pass
        ]

        orch = Orchestrator(self._make_config(), web_mode=True)
        result_qs, metadata = orch.run({"num_questions": 5, "content_summary": "test"})
        assert len(result_qs) == 5
        assert orch.last_metrics.generator_calls == 2
        assert orch.last_metrics.critic_calls == 2

    @patch("src.agents.get_provider")
    def test_max_retries_returns_partial(self, mock_get_provider):
        """After max retries, return whatever was approved."""
        mock_provider = MagicMock()
        mock_get_provider.return_value = mock_provider

        qs = [_valid_q(i) for i in range(5)]
        # Each attempt: 1 passes, 4 fail
        mixed = _mixed(1, 4)
        mock_provider.generate.side_effect = [
            json.dumps(qs),
            _structured_response(mixed),
            json.dumps(qs),
            _structured_response(mixed),
            json.dumps(qs),
            _structured_response(mixed),
        ]

        orch = Orchestrator(self._make_config(), web_mode=True)
        result_qs, metadata = orch.run({"num_questions": 5, "content_summary": "test"})
        # 3 attempts * 1 approved each = 3 questions
        assert len(result_qs) == 3
        assert orch.last_metrics.generator_calls == 3

    @patch("src.agents.get_provider")
    def test_pre_validation_filters_before_critic(self, mock_get_provider):
        """Structurally invalid questions are removed before LLM critique."""
        mock_provider = MagicMock()
        mock_get_provider.return_value = mock_provider

        good_qs = [_valid_q(0), _valid_q(1)]
        bad_q = {"type": "mc", "text": "", "points": 0}  # empty text, 0 points
        all_qs = good_qs + [bad_q]

        # Attempt 1: 3 generated, 1 fails pre-validation, 2 go to critic, both pass
        # Attempt 2: need 1 more, generate 1 good one
        mock_provider.generate.side_effect = [
            json.dumps(all_qs),  # gen: 3 (1 bad)
            _structured_response(_all_pass(2)),  # critic only sees 2 good ones
            json.dumps([_valid_q(2)]),  # gen: 1 more
            _structured_response(_all_pass(1)),  # critic passes it
        ]

        orch = Orchestrator(self._make_config(), web_mode=True)
        result_qs, metadata = orch.run({"num_questions": 3, "content_summary": "test"})
        assert len(result_qs) == 3
        assert orch.last_metrics.pre_validation_failures > 0
