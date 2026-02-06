import unittest
import time
from unittest.mock import MagicMock, patch
from src.agents import GeneratorAgent, CriticAgent, Orchestrator


class TestAgents(unittest.TestCase):
    def setUp(self):
        self.config = {
            "agent_loop": {"max_retries": 3},
            "llm": {"provider": "gemini"},
            "generation": {"sol_standards": []},
        }
        self.context = {
            "content_summary": "Summary",
            "retake_text": "Retake",
            "grade_level": "7th",
            "num_questions": 5,
        }

    @patch("src.agents.get_provider")
    @patch("src.agents.load_prompt")
    @patch("src.agents.get_qa_guidelines")
    def test_generator_success(
        self, mock_guidelines, mock_load_prompt, mock_get_provider
    ):
        mock_guidelines.return_value = "Rules"
        mock_load_prompt.return_value = "Prompt Template"

        mock_provider = MagicMock()
        mock_provider.generate.return_value = '[{"question": "test"}]'
        mock_get_provider.return_value = mock_provider

        generator = GeneratorAgent(self.config)
        result = generator.generate(self.context)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["question"], "test")
        mock_provider.generate.assert_called_once()

    @patch("src.agents.get_provider")
    @patch("src.agents.load_prompt")
    def test_critic_approved(self, mock_load_prompt, mock_get_provider):
        mock_load_prompt.return_value = "Critic Prompt"
        mock_provider = MagicMock()
        mock_provider.generate.return_value = "APPROVED"
        mock_get_provider.return_value = mock_provider

        critic = CriticAgent(self.config)
        result = critic.critique([], "guidelines", "summary")

        self.assertEqual(result["status"], "APPROVED")

    @patch("src.agents.get_provider")
    @patch("src.agents.load_prompt")
    def test_critic_rejected(self, mock_load_prompt, mock_get_provider):
        mock_load_prompt.return_value = "Critic Prompt"
        mock_provider = MagicMock()
        mock_provider.generate.return_value = "REJECTED: Too hard."
        mock_get_provider.return_value = mock_provider

        critic = CriticAgent(self.config)
        result = critic.critique([], "guidelines", "summary")

        self.assertEqual(result["status"], "REJECTED")
        self.assertIn("Too hard", result["feedback"])

    @patch("src.agents.get_provider")
    @patch("src.agents.GeneratorAgent")
    @patch("src.agents.CriticAgent")
    @patch("src.agents.get_qa_guidelines")
    def test_orchestrator_flow(self, mock_guidelines, MockCritic, MockGenerator, mock_get_provider):
        mock_guidelines.return_value = "Rules"

        # Setup mocks
        mock_gen_instance = MockGenerator.return_value
        mock_critic_instance = MockCritic.return_value

        # Scenario: First attempt rejected, second accepted
        mock_gen_instance.generate.side_effect = [
            [{"q": 1}],
            [{"q": 1, "revised": True}],
        ]
        mock_critic_instance.critique.side_effect = [
            {"status": "REJECTED", "feedback": "Fix it"},
            {"status": "APPROVED", "feedback": None},
        ]

        orch = Orchestrator(self.config)
        result = orch.run(self.context)

        self.assertEqual(result[0]["revised"], True)
        self.assertEqual(mock_gen_instance.generate.call_count, 2)
        self.assertEqual(mock_critic_instance.critique.call_count, 2)


class TestLessonContextInPrompts(unittest.TestCase):
    """Tests verifying lesson_logs and assumed_knowledge flow through the pipeline."""

    def setUp(self):
        self.config = {
            "agent_loop": {"max_retries": 3},
            "llm": {"provider": "mock"},
            "generation": {"sol_standards": []},
        }

    @patch("src.agents.get_provider")
    @patch("src.agents.load_prompt")
    @patch("src.agents.get_qa_guidelines")
    def test_generator_includes_lesson_logs_in_prompt(
        self, mock_guidelines, mock_load_prompt, mock_get_provider
    ):
        """Generator prompt should contain recent lesson topics."""
        mock_guidelines.return_value = "Rules"
        mock_load_prompt.return_value = "Grade: {grade_level}\n{sol_section}\n{class_context}"

        mock_provider = MagicMock()
        mock_provider.generate.return_value = '[{"text": "Q1", "type": "mc", "options": ["A","B","C","D"], "correct_index": 0}]'
        mock_get_provider.return_value = mock_provider

        context = {
            "content_summary": "Cells",
            "retake_text": "",
            "grade_level": "7th",
            "num_questions": 1,
            "lesson_logs": [
                {"date": "2026-02-01", "topics": ["photosynthesis", "cells"]},
                {"date": "2026-01-28", "topics": ["respiration"]},
            ],
            "assumed_knowledge": {},
        }

        generator = GeneratorAgent(self.config)
        generator.generate(context)

        # Check that the prompt sent to the LLM contains the lesson dates/topics
        call_args = mock_provider.generate.call_args[0][0]
        prompt_text = call_args[0]
        self.assertIn("photosynthesis", prompt_text)
        self.assertIn("cells", prompt_text)
        self.assertIn("2026-02-01", prompt_text)
        self.assertIn("respiration", prompt_text)

    @patch("src.agents.get_provider")
    @patch("src.agents.load_prompt")
    @patch("src.agents.get_qa_guidelines")
    def test_generator_includes_assumed_knowledge_in_prompt(
        self, mock_guidelines, mock_load_prompt, mock_get_provider
    ):
        """Generator prompt should contain assumed knowledge with depth labels."""
        mock_guidelines.return_value = "Rules"
        mock_load_prompt.return_value = "Grade: {grade_level}\n{sol_section}\n{class_context}"

        mock_provider = MagicMock()
        mock_provider.generate.return_value = '[{"text": "Q1", "type": "mc", "options": ["A","B","C","D"], "correct_index": 0}]'
        mock_get_provider.return_value = mock_provider

        context = {
            "content_summary": "Cells",
            "retake_text": "",
            "grade_level": "7th",
            "num_questions": 1,
            "lesson_logs": [],
            "assumed_knowledge": {
                "photosynthesis": {"depth": 3, "last_taught": "2026-02-01", "mention_count": 3},
                "gravity": {"depth": 1, "last_taught": "2026-01-20", "mention_count": 1},
            },
        }

        generator = GeneratorAgent(self.config)
        generator.generate(context)

        call_args = mock_provider.generate.call_args[0][0]
        prompt_text = call_args[0]
        self.assertIn("photosynthesis", prompt_text)
        self.assertIn("depth 3", prompt_text)
        self.assertIn("practiced", prompt_text)
        self.assertIn("gravity", prompt_text)
        self.assertIn("depth 1", prompt_text)
        self.assertIn("introduced", prompt_text)

    @patch("src.agents.get_provider")
    @patch("src.agents.load_prompt")
    def test_critic_receives_class_context(self, mock_load_prompt, mock_get_provider):
        """Critic prompt should contain lesson logs and assumed knowledge when provided."""
        mock_load_prompt.return_value = "Critic QA Prompt"

        mock_provider = MagicMock()
        mock_provider.generate.return_value = "APPROVED"
        mock_get_provider.return_value = mock_provider

        class_context = {
            "lesson_logs": [
                {"date": "2026-02-01", "topics": ["photosynthesis"]},
            ],
            "assumed_knowledge": {
                "photosynthesis": {"depth": 2},
            },
        }

        critic = CriticAgent(self.config)
        critic.critique(
            [{"text": "Q1"}], "guidelines", "summary",
            class_context=class_context,
        )

        call_args = mock_provider.generate.call_args[0][0]
        prompt_text = call_args[0]
        self.assertIn("photosynthesis", prompt_text)
        self.assertIn("2026-02-01", prompt_text)
        self.assertIn("depth 2", prompt_text)
        self.assertIn("reinforced", prompt_text)

    @patch("src.agents.get_provider")
    @patch("src.agents.load_prompt")
    def test_critic_works_without_class_context(self, mock_load_prompt, mock_get_provider):
        """Critic should work fine when no class_context is provided (backward compat)."""
        mock_load_prompt.return_value = "Critic QA Prompt"

        mock_provider = MagicMock()
        mock_provider.generate.return_value = "APPROVED"
        mock_get_provider.return_value = mock_provider

        critic = CriticAgent(self.config)
        result = critic.critique([{"text": "Q1"}], "guidelines", "summary")

        self.assertEqual(result["status"], "APPROVED")

    @patch("src.agents.GeneratorAgent")
    @patch("src.agents.CriticAgent")
    @patch("src.agents.get_qa_guidelines")
    def test_orchestrator_passes_class_context_to_critic(
        self, mock_guidelines, MockCritic, MockGenerator
    ):
        """Orchestrator should forward lesson_logs and assumed_knowledge to the critic."""
        mock_guidelines.return_value = "Rules"

        mock_gen_instance = MockGenerator.return_value
        mock_critic_instance = MockCritic.return_value

        mock_gen_instance.generate.return_value = [{"text": "Q1"}]
        mock_critic_instance.critique.return_value = {
            "status": "APPROVED", "feedback": None
        }

        context = {
            "content_summary": "Cells",
            "retake_text": "",
            "grade_level": "7th",
            "num_questions": 1,
            "lesson_logs": [{"date": "2026-02-01", "topics": ["cells"]}],
            "assumed_knowledge": {"cells": {"depth": 2}},
        }

        orch = Orchestrator(self.config)
        orch.run(context)

        # Verify critic was called with class_context keyword argument
        critique_call = mock_critic_instance.critique.call_args
        self.assertIn("class_context", critique_call.kwargs)
        cc = critique_call.kwargs["class_context"]
        self.assertEqual(len(cc["lesson_logs"]), 1)
        self.assertIn("cells", cc["assumed_knowledge"])

    @patch("src.agents.get_provider")
    @patch("src.agents.load_prompt")
    @patch("src.agents.get_qa_guidelines")
    def test_generator_no_lesson_context_still_works(
        self, mock_guidelines, mock_load_prompt, mock_get_provider
    ):
        """Generator should work when no lesson_logs or assumed_knowledge are in context."""
        mock_guidelines.return_value = "Rules"
        mock_load_prompt.return_value = "Grade: {grade_level}\n{sol_section}\n{class_context}"

        mock_provider = MagicMock()
        mock_provider.generate.return_value = '[{"text": "Q1", "type": "mc", "options": ["A","B"], "correct_index": 0}]'
        mock_get_provider.return_value = mock_provider

        context = {
            "content_summary": "Summary",
            "retake_text": "Retake",
            "grade_level": "7th",
            "num_questions": 1,
        }

        generator = GeneratorAgent(self.config)
        result = generator.generate(context)

        self.assertEqual(len(result), 1)
        # Prompt should NOT have "Class Context" section
        call_args = mock_provider.generate.call_args[0][0]
        prompt_text = call_args[0]
        self.assertNotIn("Class Context", prompt_text)


class TestOrchestratorCostWarnings(unittest.TestCase):
    """Tests for cost warnings and rate limit checks in the Orchestrator."""

    @patch("src.agents.get_provider")
    @patch("src.agents.check_rate_limit")
    @patch("src.agents.GeneratorAgent")
    @patch("src.agents.CriticAgent")
    @patch("src.agents.get_qa_guidelines")
    def test_orchestrator_aborts_when_rate_limit_exceeded(
        self, mock_guidelines, MockCritic, MockGenerator, mock_rate_limit, mock_get_provider
    ):
        """Pipeline should return empty list when rate limits are exceeded."""
        mock_guidelines.return_value = "Rules"
        mock_rate_limit.return_value = (True, 0, 0.0)

        config = {
            "agent_loop": {"max_retries": 3},
            "llm": {"provider": "gemini"},  # Non-mock provider
        }

        orch = Orchestrator(config)
        result = orch.run({"content_summary": "Test"})

        self.assertEqual(result, [])
        # Generator should never have been called
        MockGenerator.return_value.generate.assert_not_called()

    @patch("src.agents.check_rate_limit")
    @patch("src.agents.estimate_pipeline_cost")
    @patch("src.agents.GeneratorAgent")
    @patch("src.agents.CriticAgent")
    @patch("src.agents.get_qa_guidelines")
    def test_orchestrator_proceeds_with_mock_provider(
        self, mock_guidelines, MockCritic, MockGenerator,
        mock_estimate, mock_rate_limit
    ):
        """Mock provider should skip rate limit check entirely."""
        mock_guidelines.return_value = "Rules"

        mock_gen = MockGenerator.return_value
        mock_gen.generate.return_value = [{"text": "Q1"}]
        MockCritic.return_value.critique.return_value = {
            "status": "APPROVED", "feedback": None
        }

        config = {
            "agent_loop": {"max_retries": 3},
            "llm": {"provider": "mock"},
        }

        orch = Orchestrator(config)
        result = orch.run({"content_summary": "Test"})

        self.assertEqual(len(result), 1)
        # Rate limit should NOT have been checked for mock
        mock_rate_limit.assert_not_called()


class TestOrchestratorRetryLogic(unittest.TestCase):
    """Tests for retry logic and error handling in the Orchestrator."""

    def setUp(self):
        self.config = {
            "agent_loop": {"max_retries": 3},
            "llm": {"provider": "mock"},
        }

    @patch("src.agents.GeneratorAgent")
    @patch("src.agents.CriticAgent")
    @patch("src.agents.get_qa_guidelines")
    def test_orchestrator_retries_on_generator_exception(
        self, mock_guidelines, MockCritic, MockGenerator
    ):
        """Generator exceptions should be caught and retried."""
        mock_guidelines.return_value = "Rules"

        mock_gen = MockGenerator.return_value
        # First call throws, second succeeds
        mock_gen.generate.side_effect = [
            RuntimeError("API timeout"),
            [{"text": "Q1"}],
        ]
        MockCritic.return_value.critique.return_value = {
            "status": "APPROVED", "feedback": None
        }

        orch = Orchestrator(self.config)
        result = orch.run({"content_summary": "Test"})

        self.assertEqual(len(result), 1)
        self.assertEqual(mock_gen.generate.call_count, 2)

    @patch("src.agents.GeneratorAgent")
    @patch("src.agents.CriticAgent")
    @patch("src.agents.get_qa_guidelines")
    def test_orchestrator_aborts_after_consecutive_errors(
        self, mock_guidelines, MockCritic, MockGenerator
    ):
        """Should abort after max_errors consecutive failures."""
        mock_guidelines.return_value = "Rules"

        mock_gen = MockGenerator.return_value
        mock_gen.generate.side_effect = RuntimeError("Persistent failure")

        orch = Orchestrator(self.config)
        result = orch.run({"content_summary": "Test"})

        # Should have given up after 2 consecutive errors
        self.assertEqual(result, [])
        self.assertEqual(mock_gen.generate.call_count, 2)

    @patch("src.agents.GeneratorAgent")
    @patch("src.agents.CriticAgent")
    @patch("src.agents.get_qa_guidelines")
    def test_orchestrator_returns_draft_on_critic_exception(
        self, mock_guidelines, MockCritic, MockGenerator
    ):
        """If critic throws, return the generated draft instead of failing."""
        mock_guidelines.return_value = "Rules"

        mock_gen = MockGenerator.return_value
        mock_gen.generate.return_value = [{"text": "Q1"}]
        MockCritic.return_value.critique.side_effect = RuntimeError("Critic down")

        orch = Orchestrator(self.config)
        result = orch.run({"content_summary": "Test"})

        # Should return the draft even though critic failed
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "Q1")

    @patch("src.agents.GeneratorAgent")
    @patch("src.agents.CriticAgent")
    @patch("src.agents.get_qa_guidelines")
    def test_orchestrator_resets_error_counter_on_success(
        self, mock_guidelines, MockCritic, MockGenerator
    ):
        """Error counter should reset after a successful generation."""
        mock_guidelines.return_value = "Rules"

        mock_gen = MockGenerator.return_value
        # Error, then success rejected, then another error, then success approved
        mock_gen.generate.side_effect = [
            RuntimeError("Transient error"),
            [{"text": "Q1"}],  # success, but will be rejected
            RuntimeError("Another error"),  # this should NOT abort (counter reset)
            [{"text": "Q2"}],  # final success
        ]
        MockCritic.return_value.critique.side_effect = [
            {"status": "REJECTED", "feedback": "Fix"},
            {"status": "APPROVED", "feedback": None},
        ]

        # Need 4 retries to test this path
        config = {**self.config, "agent_loop": {"max_retries": 4}}
        orch = Orchestrator(config)
        result = orch.run({"content_summary": "Test"})

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "Q2")

    @patch("src.agents.GeneratorAgent")
    @patch("src.agents.CriticAgent")
    @patch("src.agents.get_qa_guidelines")
    def test_orchestrator_aborts_on_consecutive_empty_results(
        self, mock_guidelines, MockCritic, MockGenerator
    ):
        """Should abort after consecutive empty results from generator."""
        mock_guidelines.return_value = "Rules"

        mock_gen = MockGenerator.return_value
        mock_gen.generate.return_value = []  # Always empty

        orch = Orchestrator(self.config)
        result = orch.run({"content_summary": "Test"})

        self.assertEqual(result, [])
        # Should have tried twice before aborting
        self.assertEqual(mock_gen.generate.call_count, 2)


class TestAgentMetrics(unittest.TestCase):
    """Tests for AgentMetrics tracking."""

    def test_metrics_report_structure(self):
        """Metrics report should have all expected keys."""
        from src.agents import AgentMetrics
        m = AgentMetrics()
        m.start()
        m.generator_calls = 2
        m.critic_calls = 1
        m.errors = 0
        m.attempts = 2
        m.approved = True
        m.stop()

        report = m.report()
        self.assertIn("duration_seconds", report)
        self.assertIn("generator_calls", report)
        self.assertIn("critic_calls", report)
        self.assertIn("total_llm_calls", report)
        self.assertIn("errors", report)
        self.assertIn("attempts", report)
        self.assertIn("approved", report)
        self.assertEqual(report["total_llm_calls"], 3)
        self.assertTrue(report["approved"])

    def test_metrics_duration(self):
        """Duration should be positive after start/stop."""
        from src.agents import AgentMetrics
        m = AgentMetrics()
        m.start()
        time.sleep(0.01)
        m.stop()
        self.assertGreater(m.duration, 0)

    def test_metrics_duration_before_stop(self):
        """Duration should be 0 before stop is called."""
        from src.agents import AgentMetrics
        m = AgentMetrics()
        m.start()
        self.assertEqual(m.duration, 0.0)

    @patch("src.agents.GeneratorAgent")
    @patch("src.agents.CriticAgent")
    @patch("src.agents.get_qa_guidelines")
    def test_orchestrator_tracks_metrics(
        self, mock_guidelines, MockCritic, MockGenerator
    ):
        """Orchestrator should populate last_metrics after run."""
        mock_guidelines.return_value = "Rules"
        mock_gen = MockGenerator.return_value
        mock_gen.generate.return_value = [{"text": "Q1"}]
        MockCritic.return_value.critique.return_value = {
            "status": "APPROVED", "feedback": None
        }

        config = {
            "agent_loop": {"max_retries": 3},
            "llm": {"provider": "mock"},
        }
        orch = Orchestrator(config)
        orch.run({"content_summary": "Test"})

        self.assertIsNotNone(orch.last_metrics)
        report = orch.last_metrics.report()
        self.assertEqual(report["generator_calls"], 1)
        self.assertEqual(report["critic_calls"], 1)
        self.assertTrue(report["approved"])
        self.assertGreaterEqual(report["duration_seconds"], 0)

    @patch("src.agents.GeneratorAgent")
    @patch("src.agents.CriticAgent")
    @patch("src.agents.get_qa_guidelines")
    def test_orchestrator_metrics_on_failure(
        self, mock_guidelines, MockCritic, MockGenerator
    ):
        """Metrics should track errors on failure."""
        mock_guidelines.return_value = "Rules"
        mock_gen = MockGenerator.return_value
        mock_gen.generate.side_effect = RuntimeError("fail")

        config = {
            "agent_loop": {"max_retries": 3},
            "llm": {"provider": "mock"},
        }
        orch = Orchestrator(config)
        orch.run({"content_summary": "Test"})

        self.assertIsNotNone(orch.last_metrics)
        report = orch.last_metrics.report()
        self.assertGreater(report["errors"], 0)
        self.assertFalse(report["approved"])


if __name__ == "__main__":
    unittest.main()
