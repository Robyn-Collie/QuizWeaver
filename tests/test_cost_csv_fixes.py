"""Tests for BL-051 (cost estimate model name) and BL-053 (CSV import fixes)."""

import logging

import pytest

from src.cost_tracking import MODEL_PRICING, estimate_pipeline_cost
from src.performance_import import parse_performance_csv, validate_csv_row


# ── BL-051: Cost estimate model name fixes ──────────────────────────


class TestModelPricing:
    """MODEL_PRICING should include all current models."""

    def test_gemini_25_pro_in_pricing(self):
        assert "gemini-2.5-pro" in MODEL_PRICING

    def test_gemini_3_flash_preview_in_pricing(self):
        assert "gemini-3-flash-preview" in MODEL_PRICING

    def test_gemini_3_pro_preview_in_pricing(self):
        assert "gemini-3-pro-preview" in MODEL_PRICING

    def test_claude_sonnet_in_pricing(self):
        assert "claude-sonnet-4-20250514" in MODEL_PRICING

    def test_claude_haiku_in_pricing(self):
        assert "claude-haiku-4-5-20251001" in MODEL_PRICING


class TestEstimatePipelineCostModelDefault:
    """estimate_pipeline_cost should resolve model from provider registry."""

    def test_gemini_provider_uses_registry_default(self):
        """When no model_name is set, gemini provider should use gemini-2.5-flash."""
        config = {"llm": {"provider": "gemini"}}
        result = estimate_pipeline_cost(config)
        assert result["model"] == "gemini-2.5-flash"

    def test_gemini_pro_provider_uses_registry_default(self):
        """gemini-pro provider should default to gemini-2.5-pro."""
        config = {"llm": {"provider": "gemini-pro"}}
        result = estimate_pipeline_cost(config)
        assert result["model"] == "gemini-2.5-pro"

    def test_anthropic_provider_uses_registry_default(self):
        """anthropic provider should default to claude-sonnet model."""
        config = {"llm": {"provider": "anthropic"}}
        result = estimate_pipeline_cost(config)
        assert result["model"] == "claude-sonnet-4-20250514"

    def test_explicit_model_name_overrides_registry(self):
        """When model_name is explicitly set, it should be used."""
        config = {"llm": {"provider": "gemini", "model_name": "gemini-1.5-pro"}}
        result = estimate_pipeline_cost(config)
        assert result["model"] == "gemini-1.5-pro"

    def test_mock_provider_returns_zero_cost(self):
        """Mock provider always returns zero cost."""
        config = {"llm": {"provider": "mock"}}
        result = estimate_pipeline_cost(config)
        assert result["estimated_max_cost"] == 0.0
        assert result["provider"] == "mock"

    def test_unknown_provider_falls_back_to_gemini_25_flash(self):
        """Unknown provider falls back to gemini-2.5-flash default."""
        config = {"llm": {"provider": "unknown-provider"}}
        result = estimate_pipeline_cost(config)
        assert result["model"] == "gemini-2.5-flash"


# ── BL-053: CSV import fixes ────────────────────────────────────────


class TestCsvTotalColumn:
    """validate_csv_row should support score/total format."""

    def test_score_with_total_converts_to_percentage(self):
        """score=8, total=10 should yield avg_score=0.8."""
        row = {"topic": "photosynthesis", "score": "8", "total": "10"}
        result, error = validate_csv_row(row, 1)
        assert error is None
        assert result["avg_score"] == pytest.approx(0.8)

    def test_score_with_total_20(self):
        """score=15, total=20 should yield avg_score=0.75."""
        row = {"topic": "genetics", "score": "15", "total": "20"}
        result, error = validate_csv_row(row, 1)
        assert error is None
        assert result["avg_score"] == pytest.approx(0.75)

    def test_score_without_total_legacy_format(self):
        """score=80 (no total) should yield avg_score=0.8 as before."""
        row = {"topic": "photosynthesis", "score": "80"}
        result, error = validate_csv_row(row, 1)
        assert error is None
        assert result["avg_score"] == pytest.approx(0.8)

    def test_invalid_total_returns_error(self):
        """Non-numeric total should produce an error."""
        row = {"topic": "photosynthesis", "score": "8", "total": "abc"}
        result, error = validate_csv_row(row, 1)
        assert result is None
        assert "invalid total" in error

    def test_total_zero_ignored(self):
        """total=0 should be ignored (no division by zero)."""
        row = {"topic": "photosynthesis", "score": "80", "total": "0"}
        result, error = validate_csv_row(row, 1)
        assert error is None
        assert result["avg_score"] == pytest.approx(0.8)

    def test_empty_total_treated_as_absent(self):
        """Empty total string should be treated as absent."""
        row = {"topic": "photosynthesis", "score": "75", "total": ""}
        result, error = validate_csv_row(row, 1)
        assert error is None
        assert result["avg_score"] == pytest.approx(0.75)


class TestCsvParseWithTotal:
    """Full CSV parsing with total column."""

    def test_parse_csv_with_total_column(self):
        csv_text = "topic,score,total\nphotosynthesis,8,10\ngenetics,15,20\n"
        rows, errors = parse_performance_csv(csv_text)
        assert len(errors) == 0
        assert len(rows) == 2
        assert rows[0]["avg_score"] == pytest.approx(0.8)
        assert rows[1]["avg_score"] == pytest.approx(0.75)


class TestCsvUnknownColumns:
    """parse_performance_csv should warn about unrecognized columns."""

    def test_unknown_columns_logged(self, caplog):
        """Unrecognized columns should produce a warning log."""
        csv_text = "topic,score,grade_level,teacher_notes\nmath,80,,\n"
        with caplog.at_level(logging.WARNING, logger="src.performance_import"):
            rows, errors = parse_performance_csv(csv_text)
        assert len(rows) == 1
        assert any("Ignoring unrecognized CSV columns" in msg for msg in caplog.messages)
        # Check both unknown columns are mentioned
        warning_msg = [m for m in caplog.messages if "Ignoring unrecognized" in m][0]
        assert "grade_level" in warning_msg
        assert "teacher_notes" in warning_msg

    def test_known_columns_no_warning(self, caplog):
        """Known columns should not produce a warning."""
        csv_text = "topic,score,date,standard,total\nmath,80,2025-01-01,SOL 1.1,\n"
        with caplog.at_level(logging.WARNING, logger="src.performance_import"):
            rows, errors = parse_performance_csv(csv_text)
        assert len(rows) == 1
        assert not any("Ignoring unrecognized" in msg for msg in caplog.messages)

    def test_trailing_comma_empty_fieldname_ignored(self, caplog):
        """Trailing commas that create empty fieldnames should not warn."""
        csv_text = "topic,score,\nmath,80,\n"
        with caplog.at_level(logging.WARNING, logger="src.performance_import"):
            rows, errors = parse_performance_csv(csv_text)
        assert len(rows) == 1
        # Empty/None fieldname from trailing comma should not trigger warning
        assert not any("Ignoring unrecognized" in msg for msg in caplog.messages)
