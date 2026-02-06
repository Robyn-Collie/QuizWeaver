"""
Tests for the cost tracking module (src/cost_tracking.py).

Covers cost estimation, API call logging, cost summary aggregation,
rate limit checking, report formatting, and mock provider behavior.
"""

import os
import tempfile
import pytest

from src.cost_tracking import (
    estimate_cost,
    log_api_call,
    get_cost_summary,
    check_rate_limit,
    format_cost_report,
    estimate_pipeline_cost,
    estimate_tokens,
    summarize_lesson_context,
    MODEL_PRICING,
    DEFAULT_LOG_FILE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_temp_log():
    """Create a temp file for use as a cost log. Caller must clean up."""
    fd, path = tempfile.mkstemp(suffix=".log", prefix="cost_test_")
    os.close(fd)
    return path


def _remove_if_exists(path):
    """Remove a file if it exists, ignoring errors."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# 1. test_estimate_cost - known model pricing
# ---------------------------------------------------------------------------

class TestEstimateCost:
    def test_estimate_cost_known_model(self):
        """Verify cost calculation for a known model (gemini-1.5-flash)."""
        model = "gemini-1.5-flash"
        input_tokens = 1_000_000
        output_tokens = 1_000_000

        pricing = MODEL_PRICING[model]
        expected = pricing["input"] + pricing["output"]

        result = estimate_cost(model, input_tokens, output_tokens)
        assert result == pytest.approx(expected), (
            f"Expected {expected}, got {result}"
        )

    def test_estimate_cost_small_token_count(self):
        """Verify cost scales linearly for small token counts."""
        model = "gemini-1.5-pro"
        input_tokens = 1_000
        output_tokens = 500

        pricing = MODEL_PRICING[model]
        expected = (1_000 / 1_000_000) * pricing["input"] + (500 / 1_000_000) * pricing["output"]

        result = estimate_cost(model, input_tokens, output_tokens)
        assert result == pytest.approx(expected)

    def test_estimate_cost_zero_tokens(self):
        """Zero tokens should return zero cost."""
        result = estimate_cost("gemini-1.5-flash", 0, 0)
        assert result == 0.0

    # -------------------------------------------------------------------
    # 2. test_estimate_cost_unknown_model - falls back to default pricing
    # -------------------------------------------------------------------

    def test_estimate_cost_unknown_model(self):
        """Unknown model should use the default pricing (input=0.15, output=0.60 per 1M)."""
        model = "some-unknown-model-xyz"
        input_tokens = 2_000_000
        output_tokens = 1_000_000

        # Default pricing from the module: {"input": 0.15, "output": 0.60}
        expected = (2_000_000 / 1_000_000) * 0.15 + (1_000_000 / 1_000_000) * 0.60

        result = estimate_cost(model, input_tokens, output_tokens)
        assert result == pytest.approx(expected)


# ---------------------------------------------------------------------------
# 3. test_log_api_call - log to temp file, verify line written
# ---------------------------------------------------------------------------

class TestLogApiCall:
    def test_log_api_call(self):
        """Log an API call with explicit cost and verify the line is written."""
        log_path = _create_temp_log()
        try:
            success = log_api_call(
                provider="gemini",
                model="gemini-1.5-flash",
                input_tokens=500,
                output_tokens=200,
                cost=0.001234,
                log_file=log_path,
            )
            assert success is True
            assert os.path.exists(log_path)

            with open(log_path, "r") as f:
                lines = f.readlines()

            assert len(lines) == 1
            parts = [p.strip() for p in lines[0].split("|")]
            assert len(parts) == 6
            assert parts[1] == "gemini"
            assert parts[2] == "gemini-1.5-flash"
            assert parts[3] == "500"
            assert parts[4] == "200"
            assert "$0.001234" in parts[5]
        finally:
            _remove_if_exists(log_path)

    # -------------------------------------------------------------------
    # 4. test_log_api_call_auto_cost - cost param omitted, auto-estimated
    # -------------------------------------------------------------------

    def test_log_api_call_auto_cost(self):
        """When cost is not provided, it should be auto-estimated."""
        log_path = _create_temp_log()
        try:
            success = log_api_call(
                provider="vertex",
                model="gemini-1.5-pro",
                input_tokens=1_000_000,
                output_tokens=500_000,
                log_file=log_path,
            )
            assert success is True

            with open(log_path, "r") as f:
                line = f.readline().strip()

            parts = [p.strip() for p in line.split("|")]
            logged_cost = float(parts[5].replace("$", ""))

            expected_cost = estimate_cost("gemini-1.5-pro", 1_000_000, 500_000)
            assert logged_cost == pytest.approx(expected_cost)
        finally:
            _remove_if_exists(log_path)

    def test_log_api_call_multiple(self):
        """Multiple log calls append to the same file."""
        log_path = _create_temp_log()
        try:
            log_api_call("gemini", "gemini-1.5-flash", 100, 50, cost=0.01, log_file=log_path)
            log_api_call("vertex", "gemini-1.5-pro", 200, 100, cost=0.02, log_file=log_path)
            log_api_call("gemini", "gemini-2.5-flash", 300, 150, cost=0.03, log_file=log_path)

            with open(log_path, "r") as f:
                lines = f.readlines()
            assert len(lines) == 3
        finally:
            _remove_if_exists(log_path)


# ---------------------------------------------------------------------------
# 5. test_get_cost_summary_empty - no log file returns zeros
# ---------------------------------------------------------------------------

class TestGetCostSummary:
    def test_get_cost_summary_empty(self):
        """When log file does not exist, return zeroed summary."""
        nonexistent = os.path.join(tempfile.gettempdir(), "nonexistent_cost_log_xyz.log")
        _remove_if_exists(nonexistent)

        summary = get_cost_summary(log_file=nonexistent)

        assert summary["total_calls"] == 0
        assert summary["total_cost"] == 0.0
        assert summary["total_input_tokens"] == 0
        assert summary["total_output_tokens"] == 0
        assert summary["by_provider"] == {}
        assert summary["by_day"] == {}

    # -------------------------------------------------------------------
    # 6. test_get_cost_summary - write sample entries, verify aggregation
    # -------------------------------------------------------------------

    def test_get_cost_summary(self):
        """Write sample log entries and verify aggregated totals."""
        log_path = _create_temp_log()
        try:
            log_api_call("gemini", "gemini-1.5-flash", 1000, 500, cost=0.10, log_file=log_path)
            log_api_call("gemini", "gemini-1.5-flash", 2000, 1000, cost=0.20, log_file=log_path)
            log_api_call("vertex", "gemini-1.5-pro", 3000, 1500, cost=0.50, log_file=log_path)

            summary = get_cost_summary(log_file=log_path)

            assert summary["total_calls"] == 3
            assert summary["total_cost"] == pytest.approx(0.80)
            assert summary["total_input_tokens"] == 6000
            assert summary["total_output_tokens"] == 3000
        finally:
            _remove_if_exists(log_path)

    # -------------------------------------------------------------------
    # 7. test_get_cost_summary_by_provider - verify by_provider breakdown
    # -------------------------------------------------------------------

    def test_get_cost_summary_by_provider(self):
        """Verify the by_provider breakdown is aggregated correctly."""
        log_path = _create_temp_log()
        try:
            log_api_call("gemini", "gemini-1.5-flash", 1000, 500, cost=0.10, log_file=log_path)
            log_api_call("gemini", "gemini-1.5-flash", 2000, 1000, cost=0.20, log_file=log_path)
            log_api_call("vertex", "gemini-1.5-pro", 3000, 1500, cost=0.50, log_file=log_path)

            summary = get_cost_summary(log_file=log_path)

            assert "gemini" in summary["by_provider"]
            assert "vertex" in summary["by_provider"]

            gemini_stats = summary["by_provider"]["gemini"]
            assert gemini_stats["calls"] == 2
            assert gemini_stats["cost"] == pytest.approx(0.30)

            vertex_stats = summary["by_provider"]["vertex"]
            assert vertex_stats["calls"] == 1
            assert vertex_stats["cost"] == pytest.approx(0.50)
        finally:
            _remove_if_exists(log_path)

    def test_get_cost_summary_by_day(self):
        """Verify the by_day breakdown is present and correctly keyed."""
        log_path = _create_temp_log()
        try:
            log_api_call("gemini", "gemini-1.5-flash", 100, 50, cost=0.01, log_file=log_path)

            summary = get_cost_summary(log_file=log_path)

            assert len(summary["by_day"]) == 1
            # The key should be today's date in YYYY-MM-DD format
            from datetime import date
            today_str = date.today().isoformat()
            assert today_str in summary["by_day"]
            assert summary["by_day"][today_str]["calls"] == 1
            assert summary["by_day"][today_str]["cost"] == pytest.approx(0.01)
        finally:
            _remove_if_exists(log_path)

    def test_get_cost_summary_empty_file(self):
        """An empty log file should return zeroed summary (no crash)."""
        log_path = _create_temp_log()
        try:
            # File exists but is empty (created by _create_temp_log)
            summary = get_cost_summary(log_file=log_path)

            assert summary["total_calls"] == 0
            assert summary["total_cost"] == 0.0
        finally:
            _remove_if_exists(log_path)


# ---------------------------------------------------------------------------
# 8. test_check_rate_limit_within - under limits
# ---------------------------------------------------------------------------

class TestCheckRateLimit:
    def test_check_rate_limit_within(self):
        """When under limits, is_exceeded is False with remaining counts."""
        log_path = _create_temp_log()
        try:
            config = {
                "llm": {
                    "max_calls_per_session": 50,
                    "max_cost_per_session": 5.00,
                }
            }

            # Log a few calls (well under limits)
            log_api_call("gemini", "gemini-1.5-flash", 1000, 500, cost=0.10, log_file=log_path)
            log_api_call("gemini", "gemini-1.5-flash", 1000, 500, cost=0.10, log_file=log_path)

            is_exceeded, remaining_calls, remaining_budget = check_rate_limit(
                config, log_file=log_path
            )

            assert is_exceeded is False
            assert remaining_calls == 48
            assert remaining_budget == pytest.approx(4.80)
        finally:
            _remove_if_exists(log_path)

    # -------------------------------------------------------------------
    # 9. test_check_rate_limit_exceeded - exceed limits
    # -------------------------------------------------------------------

    def test_check_rate_limit_exceeded_by_calls(self):
        """When call count exceeds limit, is_exceeded is True."""
        log_path = _create_temp_log()
        try:
            config = {
                "llm": {
                    "max_calls_per_session": 3,
                    "max_cost_per_session": 100.00,
                }
            }

            # Log exactly 3 calls (meeting the limit)
            for _ in range(3):
                log_api_call("gemini", "gemini-1.5-flash", 100, 50, cost=0.001, log_file=log_path)

            is_exceeded, remaining_calls, remaining_budget = check_rate_limit(
                config, log_file=log_path
            )

            assert is_exceeded is True
            assert remaining_calls == 0
        finally:
            _remove_if_exists(log_path)

    def test_check_rate_limit_exceeded_by_cost(self):
        """When cost exceeds budget, is_exceeded is True."""
        log_path = _create_temp_log()
        try:
            config = {
                "llm": {
                    "max_calls_per_session": 1000,
                    "max_cost_per_session": 1.00,
                }
            }

            # Log a call that exceeds the budget
            log_api_call("vertex", "gemini-1.5-pro", 1000, 500, cost=1.50, log_file=log_path)

            is_exceeded, remaining_calls, remaining_budget = check_rate_limit(
                config, log_file=log_path
            )

            assert is_exceeded is True
            assert remaining_budget == pytest.approx(0.0)
        finally:
            _remove_if_exists(log_path)

    def test_check_rate_limit_no_log_file(self):
        """When no log file exists, all limits should show as available."""
        nonexistent = os.path.join(tempfile.gettempdir(), "nonexistent_rate_limit_xyz.log")
        _remove_if_exists(nonexistent)

        config = {
            "llm": {
                "max_calls_per_session": 50,
                "max_cost_per_session": 5.00,
            }
        }

        is_exceeded, remaining_calls, remaining_budget = check_rate_limit(
            config, log_file=nonexistent
        )

        assert is_exceeded is False
        assert remaining_calls == 50
        assert remaining_budget == pytest.approx(5.00)

    def test_check_rate_limit_defaults(self):
        """When config has no llm section, defaults are used (50 calls, $5.00)."""
        log_path = _create_temp_log()
        try:
            config = {}  # No llm config at all

            is_exceeded, remaining_calls, remaining_budget = check_rate_limit(
                config, log_file=log_path
            )

            assert is_exceeded is False
            assert remaining_calls == 50
            assert remaining_budget == pytest.approx(5.00)
        finally:
            _remove_if_exists(log_path)


# ---------------------------------------------------------------------------
# 10. test_format_cost_report - verify output format
# ---------------------------------------------------------------------------

class TestFormatCostReport:
    def test_format_cost_report_basic(self):
        """Verify the report contains expected sections and values."""
        stats = {
            "total_calls": 10,
            "total_cost": 1.2345,
            "total_input_tokens": 50000,
            "total_output_tokens": 25000,
            "by_provider": {
                "gemini": {"calls": 7, "cost": 0.80},
                "vertex": {"calls": 3, "cost": 0.4345},
            },
            "by_day": {
                "2026-02-05": {"calls": 4, "cost": 0.50},
                "2026-02-06": {"calls": 6, "cost": 0.7345},
            },
        }

        report = format_cost_report(stats)

        assert "=== API Cost Summary ===" in report
        assert "Total API calls: 10" in report
        assert "Total cost: $1.2345" in report
        assert "50,000" in report  # formatted input tokens
        assert "25,000" in report  # formatted output tokens
        assert "By Provider:" in report
        assert "gemini: 7 calls" in report
        assert "vertex: 3 calls" in report
        assert "By Day:" in report
        assert "2026-02-05" in report
        assert "2026-02-06" in report

    def test_format_cost_report_empty(self):
        """Report for zeroed stats should still produce valid output."""
        stats = {
            "total_calls": 0,
            "total_cost": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "by_provider": {},
            "by_day": {},
        }

        report = format_cost_report(stats)

        assert "=== API Cost Summary ===" in report
        assert "Total API calls: 0" in report
        assert "Total cost: $0.0000" in report
        # No provider or day sections when empty
        assert "By Provider:" not in report
        assert "By Day:" not in report

    def test_format_cost_report_warning(self):
        """When cost exceeds $5.00, a warning should appear in the report."""
        stats = {
            "total_calls": 100,
            "total_cost": 7.50,
            "total_input_tokens": 1000000,
            "total_output_tokens": 500000,
            "by_provider": {"gemini": {"calls": 100, "cost": 7.50}},
            "by_day": {},
        }

        report = format_cost_report(stats)

        assert "[WARNING] Total cost exceeds $5.00!" in report

    def test_format_cost_report_no_warning_under_threshold(self):
        """When cost is under $5.00, no warning should appear."""
        stats = {
            "total_calls": 5,
            "total_cost": 3.00,
            "total_input_tokens": 10000,
            "total_output_tokens": 5000,
            "by_provider": {"gemini": {"calls": 5, "cost": 3.00}},
            "by_day": {},
        }

        report = format_cost_report(stats)

        assert "[WARNING]" not in report


# ---------------------------------------------------------------------------
# 11. test_mock_provider_no_logging - MockLLMProvider should not log costs
# ---------------------------------------------------------------------------

class TestMockProviderNoLogging:
    def test_mock_provider_no_logging(self):
        """MockLLMProvider.generate() should NOT create or write to the cost log."""
        from src.llm_provider import MockLLMProvider

        # Use a unique temp path that should NOT be created
        log_path = os.path.join(
            tempfile.gettempdir(), "mock_provider_should_not_create_this.log"
        )
        _remove_if_exists(log_path)

        try:
            provider = MockLLMProvider()

            # Generate a response - this should not trigger cost logging
            response = provider.generate(["Test prompt for mock provider"])

            assert response is not None
            assert isinstance(response, str)

            # The mock provider should NOT have created any cost log
            # (Cost logging only happens in GeminiProvider and VertexAIProvider)
            assert not os.path.exists(log_path), (
                "MockLLMProvider should not create cost log files"
            )
        finally:
            _remove_if_exists(log_path)

    def test_mock_provider_does_not_write_default_log(self):
        """MockLLMProvider should not write to the default log file."""
        from src.llm_provider import MockLLMProvider

        default_log = DEFAULT_LOG_FILE

        # Record state before test
        existed_before = os.path.exists(default_log)
        size_before = os.path.getsize(default_log) if existed_before else 0

        provider = MockLLMProvider()
        provider.generate(["Another test prompt"])

        if existed_before:
            # File size should not have changed
            size_after = os.path.getsize(default_log)
            assert size_after == size_before, (
                "MockLLMProvider should not append to existing cost log"
            )
        else:
            # File should not have been created
            assert not os.path.exists(default_log), (
                "MockLLMProvider should not create default cost log"
            )


# ---------------------------------------------------------------------------
# Integration: round-trip test
# ---------------------------------------------------------------------------

class TestEstimatePipelineCost:
    def test_estimate_pipeline_cost_mock_provider(self):
        """Mock provider should estimate zero cost."""
        config = {"llm": {"provider": "mock"}}
        result = estimate_pipeline_cost(config, max_retries=3)

        assert result["provider"] == "mock"
        assert result["estimated_max_cost"] == 0.0
        assert result["max_calls"] == 6  # 2 calls per attempt * 3 attempts

    def test_estimate_pipeline_cost_real_provider(self):
        """Real provider should estimate non-zero cost."""
        config = {
            "llm": {
                "provider": "gemini",
                "model_name": "gemini-1.5-flash",
            }
        }
        result = estimate_pipeline_cost(config, max_retries=3)

        assert result["provider"] == "gemini"
        assert result["estimated_max_cost"] > 0
        assert result["max_calls"] == 6
        assert result["calls_per_attempt"] == 2
        assert result["max_attempts"] == 3

    def test_estimate_pipeline_cost_expensive_model(self):
        """Pro model should estimate higher cost than flash."""
        flash_config = {"llm": {"provider": "gemini", "model_name": "gemini-1.5-flash"}}
        pro_config = {"llm": {"provider": "gemini", "model_name": "gemini-1.5-pro"}}

        flash_result = estimate_pipeline_cost(flash_config)
        pro_result = estimate_pipeline_cost(pro_config)

        assert pro_result["estimated_max_cost"] > flash_result["estimated_max_cost"]

    def test_estimate_pipeline_cost_default_retries(self):
        """Default max_retries should be 3."""
        config = {"llm": {"provider": "gemini", "model_name": "gemini-1.5-flash"}}
        result = estimate_pipeline_cost(config)

        assert result["max_attempts"] == 3
        assert result["max_calls"] == 6


class TestEstimateTokens:
    def test_estimate_tokens_empty_string(self):
        """Empty string should return 0 tokens."""
        assert estimate_tokens("") == 0

    def test_estimate_tokens_none(self):
        """None-like empty input should return 0."""
        assert estimate_tokens("") == 0

    def test_estimate_tokens_short_text(self):
        """Short text should return at least 1 token."""
        result = estimate_tokens("Hi")
        assert result >= 1

    def test_estimate_tokens_known_length(self):
        """400 chars should estimate ~100 tokens."""
        text = "a" * 400
        result = estimate_tokens(text)
        assert result == 100

    def test_estimate_tokens_realistic_prompt(self):
        """A typical prompt should give reasonable estimate."""
        prompt = "You are a 7th grade teacher. Generate 10 quiz questions about photosynthesis."
        result = estimate_tokens(prompt)
        # ~80 chars -> ~20 tokens
        assert 15 <= result <= 25


class TestSummarizeLessonContext:
    def test_summarize_empty(self):
        """Empty inputs should return empty string."""
        result = summarize_lesson_context([], {})
        assert result == ""

    def test_summarize_with_lessons(self):
        """Should include lesson dates and topics."""
        logs = [
            {"date": "2026-02-01", "topics": ["photosynthesis", "cells"]},
            {"date": "2026-01-28", "topics": ["respiration"]},
        ]
        result = summarize_lesson_context(logs, {})
        assert "2026-02-01" in result
        assert "photosynthesis" in result
        assert "respiration" in result

    def test_summarize_with_knowledge(self):
        """Should include knowledge depths with short labels."""
        knowledge = {
            "photosynthesis": {"depth": 3},
            "gravity": {"depth": 1},
        }
        result = summarize_lesson_context([], knowledge)
        assert "photosynthesis" in result
        assert "pract" in result
        assert "gravity" in result
        assert "intro" in result

    def test_summarize_truncates_long_content(self):
        """Should truncate when exceeding max_chars."""
        logs = [{"date": f"2026-01-{i:02d}", "topics": [f"topic_{j}" for j in range(20)]} for i in range(1, 30)]
        knowledge = {f"topic_{i}": {"depth": i % 5 + 1} for i in range(50)}
        result = summarize_lesson_context(logs, knowledge, max_chars=500)
        assert len(result) <= 500
        assert "truncated" in result

    def test_summarize_respects_max_chars(self):
        """Result should never exceed max_chars."""
        logs = [{"date": "2026-02-01", "topics": ["a"]}]
        result = summarize_lesson_context(logs, {}, max_chars=50)
        assert len(result) <= 50


class TestIntegration:
    def test_log_then_summarize_then_format(self):
        """End-to-end: log calls, get summary, format report."""
        log_path = _create_temp_log()
        try:
            # Log several calls
            log_api_call("gemini", "gemini-1.5-flash", 5000, 2000, log_file=log_path)
            log_api_call("gemini", "gemini-2.5-flash", 10000, 5000, log_file=log_path)
            log_api_call("vertex", "gemini-1.5-pro", 8000, 3000, log_file=log_path)

            # Get summary
            summary = get_cost_summary(log_file=log_path)
            assert summary["total_calls"] == 3
            assert summary["total_input_tokens"] == 23000
            assert summary["total_output_tokens"] == 10000
            assert summary["total_cost"] > 0

            # Format report
            report = format_cost_report(summary)
            assert "=== API Cost Summary ===" in report
            assert "Total API calls: 3" in report
            assert "gemini" in report
            assert "vertex" in report

            # Check rate limit
            config = {"llm": {"max_calls_per_session": 10, "max_cost_per_session": 5.00}}
            is_exceeded, remaining_calls, remaining_budget = check_rate_limit(
                config, log_file=log_path
            )
            assert is_exceeded is False
            assert remaining_calls == 7
        finally:
            _remove_if_exists(log_path)
