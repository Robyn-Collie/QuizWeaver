"""
Tests for BL-023: Additional Deterministic Layers.

Tests cover:
- Lexile band lookups (all grade formats)
- Flesch-Kincaid text complexity estimation
- Syllable counting heuristic
- Assessment blueprint templates
- Blueprint-to-config application (question count allocation)
- Edge cases (empty text, single word, extreme values)
"""

import pytest

from src.deterministic_layers import (
    LEXILE_BANDS,
    get_lexile_band,
    get_all_lexile_bands,
    estimate_text_complexity,
    _count_syllables,
    _split_sentences,
    _split_words,
    BLUEPRINT_TEMPLATES,
    get_blueprint,
    get_available_blueprints,
    apply_blueprint_to_config,
)


class TestLexileBands:
    """Tests for Lexile/reading complexity band lookups."""

    def test_lexile_bands_has_expected_grades(self):
        """LEXILE_BANDS includes grades 2-12."""
        for g in range(2, 13):
            assert str(g) in LEXILE_BANDS

    def test_get_lexile_band_simple(self):
        band = get_lexile_band("7")
        assert band is not None
        assert band["min"] == 970
        assert band["max"] == 1120
        assert band["label"] == "Grade 7"

    def test_get_lexile_band_with_ordinal(self):
        band = get_lexile_band("8th")
        assert band is not None
        assert band["min"] == 1010

    def test_get_lexile_band_with_grade_prefix(self):
        band = get_lexile_band("Grade 6")
        assert band is not None
        assert band["min"] == 925

    def test_get_lexile_band_with_full_format(self):
        band = get_lexile_band("8th Grade")
        assert band is not None
        assert band["max"] == 1185

    def test_get_lexile_band_invalid_grade(self):
        assert get_lexile_band("K") is None
        assert get_lexile_band("") is None
        assert get_lexile_band("abc") is None

    def test_get_lexile_band_grade_1_not_in_bands(self):
        """Grade 1 is not in the bands (starts at 2)."""
        assert get_lexile_band("1") is None

    def test_get_all_lexile_bands(self):
        bands = get_all_lexile_bands()
        assert len(bands) == 11  # grades 2-12
        assert "6" in bands
        assert "12" in bands

    def test_bands_increase_with_grade(self):
        """Lexile minimums should generally increase with grade level."""
        prev_min = 0
        for g in range(2, 13):
            band = LEXILE_BANDS[str(g)]
            assert band["min"] >= prev_min
            prev_min = band["min"]


class TestSyllableCounting:
    """Tests for the deterministic syllable counting heuristic."""

    def test_single_syllable(self):
        assert _count_syllables("cat") == 1
        assert _count_syllables("dog") == 1
        assert _count_syllables("the") == 1

    def test_two_syllables(self):
        assert _count_syllables("table") == 2
        assert _count_syllables("water") == 2

    def test_three_syllables(self):
        assert _count_syllables("beautiful") == 3
        assert _count_syllables("important") == 3

    def test_empty_string(self):
        assert _count_syllables("") == 0

    def test_minimum_one_syllable(self):
        """Non-empty words should have at least 1 syllable."""
        assert _count_syllables("a") >= 1
        assert _count_syllables("I") >= 1


class TestTextComplexity:
    """Tests for Flesch-Kincaid text complexity estimation."""

    def test_simple_text(self):
        text = "The cat sat on the mat. The dog ran fast."
        result = estimate_text_complexity(text)
        assert "grade_level" in result
        assert result["grade_level"] >= 0
        assert result["total_words"] > 0
        assert result["total_sentences"] == 2

    def test_complex_text(self):
        text = (
            "The fundamental principles of thermodynamics describe the relationships "
            "between thermal energy and other manifestations of energy. The second law "
            "establishes the concept of entropy as a physical property of a thermodynamic "
            "system. The implications of these principles are far-reaching."
        )
        result = estimate_text_complexity(text)
        # Complex text should have higher grade level
        assert result["grade_level"] > 5.0

    def test_result_keys(self):
        text = "This is a test. It has two sentences."
        result = estimate_text_complexity(text)
        assert "grade_level" in result
        assert "total_words" in result
        assert "total_sentences" in result
        assert "total_syllables" in result
        assert "avg_words_per_sentence" in result
        assert "avg_syllables_per_word" in result
        assert "lexile_estimate" in result

    def test_empty_text_raises(self):
        with pytest.raises(ValueError, match="empty"):
            estimate_text_complexity("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="empty"):
            estimate_text_complexity("   ")

    def test_no_words_raises(self):
        with pytest.raises(ValueError, match="No words"):
            estimate_text_complexity("123 456 789")

    def test_lexile_estimate_format(self):
        text = "The student will read and demonstrate comprehension of fictional texts."
        result = estimate_text_complexity(text)
        # Should be a string like "970L-1120L"
        assert isinstance(result["lexile_estimate"], str)
        assert "L" in result["lexile_estimate"]

    def test_grade_level_non_negative(self):
        text = "Go. Run. Jump. Stop."
        result = estimate_text_complexity(text)
        assert result["grade_level"] >= 0.0

    def test_single_sentence_no_period(self):
        """Text without sentence-ending punctuation is treated as one sentence."""
        text = "The quick brown fox jumps over the lazy dog"
        result = estimate_text_complexity(text)
        assert result["total_sentences"] == 1


class TestSplitHelpers:
    """Tests for sentence and word splitting."""

    def test_split_sentences_basic(self):
        sentences = _split_sentences("Hello world. How are you? I am fine!")
        assert len(sentences) == 3

    def test_split_sentences_empty(self):
        assert _split_sentences("") == []

    def test_split_words_basic(self):
        words = _split_words("Hello world, this is a test.")
        assert "Hello" in words
        assert "world" in words
        assert len(words) == 6

    def test_split_words_handles_punctuation(self):
        words = _split_words("It's a dog's life.")
        assert "It's" in words
        assert "dog's" in words


class TestBlueprintTemplates:
    """Tests for assessment blueprint templates."""

    def test_blueprint_templates_has_expected_keys(self):
        assert "balanced" in BLUEPRINT_TEMPLATES
        assert "higher_order" in BLUEPRINT_TEMPLATES
        assert "foundational" in BLUEPRINT_TEMPLATES

    def test_each_template_sums_to_100(self):
        """Every blueprint distribution sums to 100%."""
        for name, bp in BLUEPRINT_TEMPLATES.items():
            total = sum(bp["distribution"].values())
            assert total == 100, f"Blueprint '{name}' sums to {total}, not 100"

    def test_each_template_has_all_blooms_levels(self):
        """Every blueprint has Remember through Create."""
        expected_levels = {"Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"}
        for name, bp in BLUEPRINT_TEMPLATES.items():
            assert set(bp["distribution"].keys()) == expected_levels, (
                f"Blueprint '{name}' missing levels"
            )

    def test_get_blueprint(self):
        bp = get_blueprint("balanced")
        assert bp is not None
        assert bp["label"] == "Balanced Assessment"
        assert "distribution" in bp

    def test_get_blueprint_unknown(self):
        assert get_blueprint("nonexistent") is None

    def test_get_available_blueprints(self):
        bps = get_available_blueprints()
        assert len(bps) >= 3
        keys = [b["key"] for b in bps]
        assert "balanced" in keys
        for b in bps:
            assert "key" in b
            assert "label" in b
            assert "description" in b
            assert "distribution" in b


class TestApplyBlueprint:
    """Tests for apply_blueprint_to_config."""

    def test_balanced_20_questions(self):
        result = apply_blueprint_to_config("balanced", 20)
        total = sum(result.values())
        assert total == 20
        assert result["Remember"] == 3  # 15% of 20 = 3
        assert result["Understand"] == 5  # 25% of 20 = 5
        assert result["Apply"] == 5  # 25% of 20 = 5

    def test_higher_order_10_questions(self):
        result = apply_blueprint_to_config("higher_order", 10)
        total = sum(result.values())
        assert total == 10
        # Higher order should have more Analyze/Evaluate/Create
        assert result["Analyze"] >= result["Remember"]

    def test_foundational_15_questions(self):
        result = apply_blueprint_to_config("foundational", 15)
        total = sum(result.values())
        assert total == 15
        # Foundational emphasizes Remember + Understand
        assert result["Remember"] + result["Understand"] >= 8

    def test_apply_single_question(self):
        """Edge case: only 1 question."""
        result = apply_blueprint_to_config("balanced", 1)
        total = sum(result.values())
        assert total == 1

    def test_unknown_blueprint_raises(self):
        with pytest.raises(ValueError, match="Unknown blueprint"):
            apply_blueprint_to_config("nonexistent", 10)

    def test_zero_questions_raises(self):
        with pytest.raises(ValueError, match="question_count must be at least 1"):
            apply_blueprint_to_config("balanced", 0)

    def test_large_question_count(self):
        result = apply_blueprint_to_config("balanced", 100)
        total = sum(result.values())
        assert total == 100
        # Exact percentages for balanced at 100
        assert result["Remember"] == 15
        assert result["Understand"] == 25
        assert result["Apply"] == 25
        assert result["Analyze"] == 20
        assert result["Evaluate"] == 10
        assert result["Create"] == 5

    def test_all_blueprints_produce_correct_total(self):
        """Every blueprint should produce exact total for various counts."""
        for name in BLUEPRINT_TEMPLATES:
            for count in [1, 5, 10, 20, 25, 50]:
                result = apply_blueprint_to_config(name, count)
                total = sum(result.values())
                assert total == count, (
                    f"Blueprint '{name}' with {count} questions: got {total}"
                )

    def test_result_has_all_cognitive_levels(self):
        result = apply_blueprint_to_config("balanced", 10)
        expected_levels = {"Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"}
        assert set(result.keys()) == expected_levels
