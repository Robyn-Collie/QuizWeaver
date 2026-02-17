"""
Tests for the deterministic pre-validation layer (src/critic_validation.py).

Covers structural checks, type-specific rules, basic fact-consistency,
and teacher_config filtering.  ~25 tests.
"""

from src.critic_validation import VALID_TYPES, pre_validate_questions

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mc(text="What is X?", options=None, correct_index=0, points=1, **kw):
    q = {
        "type": "mc",
        "text": text,
        "options": options or ["A", "B", "C", "D"],
        "correct_index": correct_index,
        "points": points,
    }
    q.update(kw)
    return q


def _tf(text="The sky is blue.", is_true=True, points=1, **kw):
    q = {"type": "tf", "text": text, "is_true": is_true, "points": points}
    q.update(kw)
    return q


def _sa(text="Explain X.", expected_answer="X is Y.", points=1, **kw):
    q = {"type": "short_answer", "text": text, "expected_answer": expected_answer, "points": points}
    q.update(kw)
    return q


def _fill(text="Water is ___ at 100C.", correct_answer="boiling", points=1, **kw):
    q = {"type": "fill_in_blank", "text": text, "correct_answer": correct_answer, "points": points}
    q.update(kw)
    return q


def _ordering(text="Order these steps.", items=None, correct_order=None, points=1, **kw):
    q = {
        "type": "ordering",
        "text": text,
        "items": items or ["Step 1", "Step 2", "Step 3"],
        "correct_order": correct_order or [0, 1, 2],
        "points": points,
    }
    q.update(kw)
    return q


# ---------------------------------------------------------------------------
# Common field checks
# ---------------------------------------------------------------------------


class TestCommonFields:
    def test_valid_mc_passes(self):
        results = pre_validate_questions([_mc()])
        assert results[0]["passed"] is True
        assert results[0]["issues"] == []

    def test_missing_text(self):
        q = _mc()
        del q["text"]
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False
        assert any("text" in i.lower() for i in results[0]["issues"])

    def test_empty_text(self):
        results = pre_validate_questions([_mc(text="")])
        assert results[0]["passed"] is False

    def test_missing_points(self):
        q = _mc()
        del q["points"]
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False
        assert any("points" in i.lower() for i in results[0]["issues"])

    def test_zero_points(self):
        results = pre_validate_questions([_mc(points=0)])
        assert results[0]["passed"] is False

    def test_negative_points(self):
        results = pre_validate_questions([_mc(points=-1)])
        assert results[0]["passed"] is False

    def test_missing_type(self):
        q = {"text": "Question?", "points": 1}
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False
        assert any("type" in i.lower() for i in results[0]["issues"])

    def test_unrecognised_type(self):
        q = {"type": "banana", "text": "Q?", "points": 1}
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False
        assert any("banana" in i for i in results[0]["issues"])

    def test_all_valid_types_recognised(self):
        """Every type in VALID_TYPES should be accepted (common-field level)."""
        for t in VALID_TYPES:
            q = {"type": t, "text": "Q?", "points": 1}
            # Add minimal type-specific fields so they don't fail on type checks
            if t == "mc":
                q.update({"options": ["A", "B", "C", "D"], "correct_index": 0})
            elif t == "tf":
                q["is_true"] = True
            elif t == "short_answer":
                q["expected_answer"] = "answer"
            elif t == "fill_in_blank":
                q["text"] = "The ___ is blue."
                q["correct_answer"] = "sky"
            elif t == "ordering":
                q["items"] = ["A", "B"]
                q["correct_order"] = [0, 1]
            elif t == "ma":
                q.update({"options": ["A", "B"], "correct_indices": [0]})
            elif t == "matching":
                q["matches"] = [{"term": "A", "definition": "1"}, {"term": "B", "definition": "2"}]
            elif t == "stimulus":
                q["stimulus_text"] = "A passage about cells."
                q["sub_questions"] = [{"type": "mc", "text": "Q?", "points": 1}]
            results = pre_validate_questions([q])
            assert results[0]["passed"] is True, f"Type '{t}' should pass: {results[0]['issues']}"


# ---------------------------------------------------------------------------
# MC-specific
# ---------------------------------------------------------------------------


class TestMCValidation:
    def test_mc_missing_options(self):
        q = _mc()
        del q["options"]
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False

    def test_mc_too_few_options(self):
        results = pre_validate_questions([_mc(options=["A"])])
        assert results[0]["passed"] is False

    def test_mc_missing_correct_index(self):
        q = _mc()
        del q["correct_index"]
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False

    def test_mc_correct_index_out_of_bounds(self):
        results = pre_validate_questions([_mc(correct_index=5)])
        assert results[0]["passed"] is False

    def test_mc_correct_answer_mismatch_warning(self):
        """correct_answer != options[correct_index] -> fact warning."""
        q = _mc(correct_answer="Wrong text")
        results = pre_validate_questions([q])
        assert results[0]["passed"] is True  # warning, not failure
        assert len(results[0]["fact_warnings"]) > 0

    def test_mc_correct_answer_matches_no_warning(self):
        q = _mc(options=["Alpha", "Beta", "Gamma", "Delta"], correct_index=1, correct_answer="Beta")
        results = pre_validate_questions([q])
        assert results[0]["fact_warnings"] == []


# ---------------------------------------------------------------------------
# TF-specific
# ---------------------------------------------------------------------------


class TestTFValidation:
    def test_tf_valid(self):
        results = pre_validate_questions([_tf()])
        assert results[0]["passed"] is True

    def test_tf_missing_is_true(self):
        q = _tf()
        del q["is_true"]
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False

    def test_tf_is_true_not_bool(self):
        results = pre_validate_questions([_tf(is_true="yes")])
        assert results[0]["passed"] is False

    def test_tf_contradicts_correct_answer(self):
        """is_true=True but correct_answer='False' -> fact warning."""
        q = _tf(is_true=True, correct_answer="False")
        results = pre_validate_questions([q])
        assert results[0]["passed"] is True  # warning, not failure
        assert len(results[0]["fact_warnings"]) > 0

    def test_tf_consistent_correct_answer(self):
        q = _tf(is_true=True, correct_answer="True")
        results = pre_validate_questions([q])
        assert results[0]["fact_warnings"] == []


# ---------------------------------------------------------------------------
# Short-answer / fill-in / ordering
# ---------------------------------------------------------------------------


class TestOtherTypeValidation:
    def test_sa_missing_expected_answer(self):
        q = _sa()
        del q["expected_answer"]
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False

    def test_fill_missing_blank(self):
        results = pre_validate_questions([_fill(text="No blank here")])
        assert results[0]["passed"] is False

    def test_fill_missing_correct_answer(self):
        q = _fill()
        del q["correct_answer"]
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False

    def test_ordering_valid(self):
        results = pre_validate_questions([_ordering()])
        assert results[0]["passed"] is True

    def test_ordering_missing_items(self):
        q = _ordering()
        del q["items"]
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False

    def test_ordering_missing_correct_order(self):
        q = _ordering()
        del q["correct_order"]
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False

    def test_matching_valid(self):
        q = {
            "type": "matching",
            "text": "Match the term to its definition.",
            "points": 1,
            "matches": [
                {"term": "H2O", "definition": "Water"},
                {"term": "NaCl", "definition": "Salt"},
            ],
        }
        results = pre_validate_questions([q])
        assert results[0]["passed"] is True

    def test_matching_missing_matches(self):
        q = {"type": "matching", "text": "Match terms.", "points": 1}
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False
        assert any("matches" in i.lower() or "missing" in i.lower() for i in results[0]["issues"])

    def test_matching_empty_matches(self):
        q = {"type": "matching", "text": "Match terms.", "points": 1, "matches": []}
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False

    def test_matching_one_pair_insufficient(self):
        q = {
            "type": "matching",
            "text": "Match.",
            "points": 1,
            "matches": [{"term": "A", "definition": "B"}],
        }
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False
        assert any("at least 2" in i for i in results[0]["issues"])

    def test_matching_missing_term_in_pair(self):
        q = {
            "type": "matching",
            "text": "Match.",
            "points": 1,
            "matches": [
                {"term": "A", "definition": "B"},
                {"term": "", "definition": "D"},
            ],
        }
        results = pre_validate_questions([q])
        assert results[0]["passed"] is False

    def test_matching_prompt_response_alternate_shape(self):
        """Alternate data shape with prompt_items/response_items."""
        q = {
            "type": "matching",
            "text": "Match.",
            "points": 1,
            "prompt_items": ["A", "B", "C"],
            "response_items": ["1", "2", "3"],
        }
        results = pre_validate_questions([q])
        assert results[0]["passed"] is True


# ---------------------------------------------------------------------------
# Teacher config filtering
# ---------------------------------------------------------------------------


class TestTeacherConfig:
    def test_allowed_types_filters(self):
        qs = [_mc(), _tf()]
        config = {"allowed_types": ["mc"]}
        results = pre_validate_questions(qs, teacher_config=config)
        assert results[0]["passed"] is True  # mc allowed
        assert results[1]["passed"] is False  # tf not allowed

    def test_no_config_allows_all(self):
        results = pre_validate_questions([_mc(), _tf(), _sa()])
        assert all(r["passed"] for r in results)


# ---------------------------------------------------------------------------
# Multiple questions / indices
# ---------------------------------------------------------------------------


class TestMultipleQuestions:
    def test_indices_match(self):
        qs = [_mc(), _tf(), _sa()]
        results = pre_validate_questions(qs)
        for i, r in enumerate(results):
            assert r["index"] == i

    def test_mixed_pass_fail(self):
        good = _mc()
        bad = _mc()
        del bad["options"]
        results = pre_validate_questions([good, bad])
        assert results[0]["passed"] is True
        assert results[1]["passed"] is False
