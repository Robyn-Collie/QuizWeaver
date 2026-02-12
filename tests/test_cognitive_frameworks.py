"""
Tests for the cognitive frameworks constants module (src/cognitive_frameworks.py).

Tests cover:
  - get_framework returns correct levels for blooms and dok
  - get_framework returns None for unknown frameworks
  - Level dicts have required keys
  - validate_distribution passes for valid distributions
  - validate_distribution fails for sum mismatch, invalid levels, negative counts
  - QUESTION_TYPES has expected entries

Run with: python -m pytest tests/test_cognitive_frameworks.py -v
"""

import os
import sys

# Ensure project root is on sys.path so imports work when running standalone.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.cognitive_frameworks import (
    QUESTION_TYPES,
    get_framework,
    validate_distribution,
)


class TestGetFramework:
    """Tests for get_framework()."""

    def test_blooms_returns_six_levels(self):
        levels = get_framework("blooms")
        assert levels is not None
        assert len(levels) == 6

    def test_dok_returns_four_levels(self):
        levels = get_framework("dok")
        assert levels is not None
        assert len(levels) == 4

    def test_unknown_returns_none(self):
        assert get_framework("unknown") is None
        assert get_framework("") is None

    def test_blooms_levels_have_required_keys(self):
        for level in get_framework("blooms"):
            assert "number" in level
            assert "name" in level
            assert "description" in level
            assert "color" in level

    def test_dok_levels_have_required_keys(self):
        for level in get_framework("dok"):
            assert "number" in level
            assert "name" in level
            assert "description" in level
            assert "color" in level

    def test_blooms_numbers_sequential(self):
        levels = get_framework("blooms")
        numbers = [lvl["number"] for lvl in levels]
        assert numbers == [1, 2, 3, 4, 5, 6]

    def test_dok_numbers_sequential(self):
        levels = get_framework("dok")
        numbers = [lvl["number"] for lvl in levels]
        assert numbers == [1, 2, 3, 4]


class TestValidateDistribution:
    """Tests for validate_distribution()."""

    def test_valid_blooms_distribution(self):
        dist = {1: 5, 2: 5, 3: 4, 4: 3, 5: 2, 6: 1}
        ok, msg = validate_distribution("blooms", dist, 20)
        assert ok is True
        assert msg == ""

    def test_valid_dok_distribution(self):
        dist = {1: 3, 2: 3, 3: 2, 4: 2}
        ok, msg = validate_distribution("dok", dist, 10)
        assert ok is True
        assert msg == ""

    def test_string_keys_accepted(self):
        dist = {"1": 5, "2": 5, "3": 4, "4": 3, "5": 2, "6": 1}
        ok, msg = validate_distribution("blooms", dist, 20)
        assert ok is True

    def test_fails_when_sum_not_equal_to_total(self):
        dist = {1: 5, 2: 5}
        ok, msg = validate_distribution("blooms", dist, 20)
        assert ok is False
        assert "10" in msg and "20" in msg

    def test_fails_for_invalid_level_numbers(self):
        dist = {1: 5, 2: 5, 99: 10}
        ok, msg = validate_distribution("blooms", dist, 20)
        assert ok is False
        assert "99" in msg

    def test_fails_for_negative_counts(self):
        dist = {1: -3, 2: 5, 3: 4, 4: 3, 5: 2, 6: 9}
        ok, msg = validate_distribution("blooms", dist, 20)
        assert ok is False
        assert "Negative" in msg or "negative" in msg

    def test_fails_for_unknown_framework(self):
        ok, msg = validate_distribution("unknown", {1: 10}, 10)
        assert ok is False
        assert "Unknown framework" in msg

    def test_partial_levels_valid_if_sum_matches(self):
        dist = {1: 10}
        ok, msg = validate_distribution("blooms", dist, 10)
        assert ok is True

    def test_zero_counts_valid(self):
        dist = {1: 0, 2: 0, 3: 0, 4: 10}
        ok, msg = validate_distribution("dok", dist, 10)
        assert ok is True


class TestQuestionTypes:
    """Tests for the QUESTION_TYPES constant."""

    def test_has_six_entries(self):
        assert len(QUESTION_TYPES) == 6

    def test_expected_types_present(self):
        expected = {"mc", "tf", "fill_in_blank", "short_answer", "matching", "essay"}
        assert set(QUESTION_TYPES) == expected
