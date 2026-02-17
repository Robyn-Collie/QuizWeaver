"""
Simple tests for MockLLMProvider (no pytest required).
Run with: python tests/test_mock_provider_simple.py
"""

import json
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.llm_provider import LLMProvider, MockLLMProvider


def test_mock_provider_inherits_from_base():
    """Test that MockLLMProvider implements LLMProvider interface."""
    provider = MockLLMProvider()
    assert isinstance(provider, LLMProvider), "MockLLMProvider should inherit from LLMProvider"
    assert hasattr(provider, "generate"), "Should have generate method"
    assert hasattr(provider, "prepare_image_context"), "Should have prepare_image_context method"
    print("[PASS] Mock provider inherits from base class")


def test_mock_provider_returns_valid_json():
    """Test that mock provider returns valid JSON."""
    provider = MockLLMProvider()
    prompt = ["Generate quiz questions about photosynthesis"]
    response = provider.generate(prompt, json_mode=True)

    try:
        data = json.loads(response)
        assert data is not None, "Response should not be None"
        print("[PASS] Mock provider returns valid JSON")
    except json.JSONDecodeError as e:
        raise AssertionError(f"Mock provider did not return valid JSON: {e}")


def test_analyst_response_schema():
    """Test that analyst response matches expected schema."""
    provider = MockLLMProvider()
    prompt = ["Analyze the style and determine question count"]
    response = provider.generate(prompt, json_mode=False)

    data = json.loads(response)

    assert "estimated_question_count" in data, "Missing estimated_question_count"
    assert "image_ratio" in data, "Missing image_ratio"
    assert isinstance(data["estimated_question_count"], int), "question_count should be int"
    assert isinstance(data["image_ratio"], (int, float)), "image_ratio should be numeric"
    assert 0 <= data["image_ratio"] <= 1, "image_ratio should be between 0 and 1"
    print("[PASS] Analyst response schema is correct")


def test_generator_response_schema():
    """Test that generator response matches expected schema."""
    provider = MockLLMProvider()
    prompt = ["Generate quiz questions about cell division"]
    response = provider.generate(prompt, json_mode=True)

    data = json.loads(response)

    assert isinstance(data, list), "Generator should return a list"
    assert len(data) > 0, "Should generate at least one question"

    question = data[0]
    assert "type" in question, "Question should have type"
    assert "text" in question, "Question should have text"
    assert "points" in question, "Question should have points"
    assert question["type"] in [
        "multiple_choice",
        "true_false",
        "ordering",
        "short_answer",
        "fill_in",
        "multiple_answer",
        "stimulus",
        "ma",
    ], f"Invalid question type: {question['type']}"
    print("[PASS] Generator response schema is correct")


def test_critic_response_schema():
    """Test that critic response matches structured per-question verdict schema."""
    provider = MockLLMProvider()
    prompt = ["Review these questions and provide feedback"]
    response = provider.generate(prompt, json_mode=False)

    data = json.loads(response)

    assert "questions" in data, "Critic response should have questions array"
    assert "overall_notes" in data, "Critic response should have overall_notes"
    assert isinstance(data["questions"], list), "questions should be a list"
    for verdict in data["questions"]:
        assert "index" in verdict, "Each verdict should have index"
        assert "verdict" in verdict, "Each verdict should have verdict"
        assert verdict["verdict"] in ("PASS", "FAIL"), "Invalid verdict"
        assert "fact_check" in verdict, "Each verdict should have fact_check"
    print("[PASS] Critic response schema is correct")


def test_no_external_calls():
    """Test that mock provider makes no external API calls."""
    provider = MockLLMProvider()
    prompt = ["Test prompt"]

    try:
        response = provider.generate(prompt)
        assert response is not None, "Should return a response"
        print("[PASS] No external API calls made (no errors)")
    except Exception as e:
        if "API" in str(e) or "key" in str(e).lower():
            raise AssertionError(f"Mock provider attempted external API call: {e}")


def test_prepare_image_context():
    """Test that prepare_image_context returns a mock object."""
    provider = MockLLMProvider()
    mock_path = "/fake/path/to/image.png"
    result = provider.prepare_image_context(mock_path)

    assert result is not None, "Should return something"
    assert isinstance(result, str), "Should return a string"
    assert "Mock" in result or mock_path in result, "Should indicate it's a mock"
    print("[PASS] prepare_image_context returns mock object")


def test_interface_compatibility():
    """Test that MockLLMProvider is compatible with real providers."""
    provider = MockLLMProvider()

    # Should accept same parameters as real providers
    result1 = provider.generate(["test"], json_mode=False)
    assert result1 is not None, "Should handle json_mode=False"

    result2 = provider.generate(["test"], json_mode=True)
    assert result2 is not None, "Should handle json_mode=True"

    print("[PASS] Interface compatible with real providers")


def run_all_tests():
    """Run all tests."""
    tests = [
        test_mock_provider_inherits_from_base,
        test_mock_provider_returns_valid_json,
        test_analyst_response_schema,
        test_generator_response_schema,
        test_critic_response_schema,
        test_no_external_calls,
        test_prepare_image_context,
        test_interface_compatibility,
    ]

    print("\n=== Running MockLLMProvider Tests ===\n")

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: Unexpected error: {e}")
            failed += 1

    print("\n=== Test Results ===")
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")

    if failed > 0:
        sys.exit(1)
    else:
        print("\n[OK] All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    run_all_tests()
