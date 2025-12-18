import unittest
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

    @patch("src.agents.GeneratorAgent")
    @patch("src.agents.CriticAgent")
    @patch("src.agents.get_qa_guidelines")
    def test_orchestrator_flow(self, mock_guidelines, MockCritic, MockGenerator):
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


if __name__ == "__main__":
    unittest.main()
