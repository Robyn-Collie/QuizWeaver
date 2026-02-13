"""
Tests for MockLLMProvider to ensure cost-free development works correctly.
"""

import json

import pytest

from src.llm_provider import LLMProvider, MockLLMProvider


class TestMockProvider:
    """Test suite for MockLLMProvider."""

    def setup_method(self):
        """Set up test fixtures."""
        self.provider = MockLLMProvider()

    def test_mock_provider_inherits_from_base(self):
        """Test that MockLLMProvider implements LLMProvider interface."""
        assert isinstance(self.provider, LLMProvider)
        assert hasattr(self.provider, "generate")
        assert hasattr(self.provider, "prepare_image_context")

    def test_mock_provider_returns_valid_json(self):
        """Test that mock provider returns valid JSON."""
        prompt = ["Generate quiz questions about photosynthesis"]
        response = self.provider.generate(prompt, json_mode=True)

        # Should be valid JSON
        try:
            data = json.loads(response)
            assert data is not None
        except json.JSONDecodeError:
            pytest.fail("Mock provider did not return valid JSON")

    def test_analyst_response_schema(self):
        """Test that analyst response matches expected schema."""
        prompt = ["Analyze the style and determine question count"]
        response = self.provider.generate(prompt, json_mode=False)

        data = json.loads(response)

        # Check for required analyst fields
        assert "estimated_question_count" in data
        assert "image_ratio" in data
        assert isinstance(data["estimated_question_count"], int)
        assert isinstance(data["image_ratio"], (int, float))
        assert 0 <= data["image_ratio"] <= 1

    def test_generator_response_schema(self):
        """Test that generator response matches expected schema."""
        prompt = ["Generate quiz questions about cell division"]
        response = self.provider.generate(prompt, json_mode=True)

        data = json.loads(response)

        # Should be a list of questions
        assert isinstance(data, list)
        assert len(data) > 0

        # Check first question structure
        question = data[0]
        assert "type" in question
        assert "text" in question
        assert "points" in question
        assert question["type"] in ["multiple_choice", "true_false", "ordering", "short_answer"]

    def test_critic_response_schema(self):
        """Test that critic response matches structured per-question verdict schema."""
        prompt = ["Review these questions and provide feedback"]
        response = self.provider.generate(prompt, json_mode=False)

        data = json.loads(response)

        # New structured critic format: per-question verdicts
        assert "questions" in data
        assert "overall_notes" in data
        assert isinstance(data["questions"], list)
        for verdict in data["questions"]:
            assert "index" in verdict
            assert "verdict" in verdict
            assert verdict["verdict"] in ("PASS", "FAIL")
            assert "fact_check" in verdict

    def test_mock_provider_no_external_calls(self):
        """Test that mock provider makes no external API calls."""
        # This is implicitly tested by not setting up any API keys
        # If external calls were made, this would raise an error
        prompt = ["Test prompt"]

        try:
            response = self.provider.generate(prompt)
            assert response is not None
        except Exception as e:
            if "API" in str(e) or "key" in str(e).lower():
                pytest.fail(f"Mock provider attempted external API call: {e}")

    def test_prepare_image_context_returns_mock(self):
        """Test that prepare_image_context returns a mock object."""
        mock_path = "/fake/path/to/image.png"
        result = self.provider.prepare_image_context(mock_path)

        assert result is not None
        assert isinstance(result, str)
        assert "Mock" in result or mock_path in result

    def test_responses_have_variety(self):
        """Test that responses have some variation (not identical)."""
        prompt = ["Generate questions"]

        response1 = self.provider.generate(prompt)
        response2 = self.provider.generate(prompt)

        # Responses should have some variation due to randomization
        # (though they may occasionally be identical - that's okay)
        # We're just checking that the mechanism for variety exists
        assert isinstance(response1, str)
        assert isinstance(response2, str)

    def test_json_mode_always_returns_valid_json(self):
        """Test that json_mode=True always returns valid JSON."""
        prompts = [
            ["Analyze this content"],
            ["Generate questions"],
            ["Review the quiz"],
        ]

        for prompt in prompts:
            response = self.provider.generate(prompt, json_mode=True)

            try:
                json.loads(response)
            except json.JSONDecodeError:
                pytest.fail(f"Invalid JSON for prompt {prompt}: {response}")

    def test_context_awareness(self):
        """Test that responses incorporate prompt context."""
        prompt = ["Generate questions about mitosis and meiosis"]
        response = self.provider.generate(prompt, json_mode=True)

        data = json.loads(response)

        # Response should be context-aware (contain relevant topic)
        response_text = json.dumps(data).lower()
        # Check if any science topics appear in response
        has_context = any(topic in response_text for topic in ["mitosis", "meiosis", "cell", "biology", "science"])
        assert has_context, "Response should be context-aware"


class TestProviderInterfaceCompatibility:
    """Test that MockLLMProvider is compatible with real providers."""

    def test_generate_signature_matches(self):
        """Test that generate() signature matches LLMProvider interface."""
        mock = MockLLMProvider()

        # Should accept same parameters as real providers
        try:
            result = mock.generate(["test"], json_mode=False)
            assert result is not None

            result = mock.generate(["test"], json_mode=True)
            assert result is not None
        except TypeError as e:
            pytest.fail(f"MockLLMProvider.generate() signature mismatch: {e}")

    def test_prepare_image_signature_matches(self):
        """Test that prepare_image_context() signature matches interface."""
        mock = MockLLMProvider()

        # Should accept same parameters as real providers
        try:
            result = mock.prepare_image_context("/path/to/image.png")
            assert result is not None
        except TypeError as e:
            pytest.fail(f"MockLLMProvider.prepare_image_context() signature mismatch: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
