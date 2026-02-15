"""
Tests for the pre-generation cost estimate API endpoint (/api/estimate-cost).

Covers:
- Mock provider returns $0.00 with is_mock=True
- Real provider name returns non-zero estimate
- Invalid/missing parameters handled gracefully
- Cost estimate div appears on quiz generation form
- Cost estimate div appears on exit ticket form
- Question count scaling works correctly
- Warning threshold for expensive estimates
"""

import json
import os
import tempfile

import pytest

from src.database import Base, Class, get_engine, get_session


@pytest.fixture
def app_with_mock():
    """Flask app configured with mock provider."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    cls = Class(
        name="Test Class",
        grade_level="8th Grade",
        subject="Science",
        standards=json.dumps(["SOL 8.1"]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()
    session.close()
    engine.dispose()

    from src.web.app import create_app

    config = {
        "paths": {"database_file": db_path},
        "llm": {"provider": "mock"},
        "generation": {
            "default_grade_level": "8th Grade",
            "quiz_title": "Test",
            "sol_standards": [],
            "target_image_ratio": 0.0,
            "generate_ai_images": False,
            "interactive_review": False,
        },
    }
    app = create_app(config)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    yield app, db_path

    app.config["DB_ENGINE"].dispose()
    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def client(app_with_mock):
    """Logged-in test client."""
    app, _ = app_with_mock
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["logged_in"] = True
            sess["username"] = "teacher"
        yield c


# ============================================================
# API endpoint tests
# ============================================================


class TestEstimateCostAPI:
    """Tests for /api/estimate-cost endpoint."""

    def test_mock_provider_returns_zero(self, client):
        """Mock provider should return $0.00 and is_mock=True."""
        resp = client.get("/api/estimate-cost")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["estimated_cost"] == "$0.00"
        assert data["is_mock"] is True
        assert data["model"] == "mock"

    def test_mock_provider_with_explicit_param(self, client):
        """Explicitly passing provider=mock returns free estimate."""
        resp = client.get("/api/estimate-cost?provider=mock&num_questions=20")
        data = resp.get_json()
        assert data["is_mock"] is True
        assert data["estimated_cost"] == "$0.00"

    def test_real_provider_returns_nonzero(self, client):
        """A known real provider should return a non-zero cost."""
        resp = client.get("/api/estimate-cost?provider=gemini&num_questions=10")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["is_mock"] is False
        assert data["estimated_cost"] != "$0.00"
        assert data["estimated_tokens"] > 0
        assert data["model"] == "gemini-2.5-flash"

    def test_question_count_scales_cost(self, client):
        """More questions should increase the estimated cost."""
        resp_10 = client.get("/api/estimate-cost?provider=gemini&num_questions=10")
        resp_30 = client.get("/api/estimate-cost?provider=gemini&num_questions=30")
        data_10 = resp_10.get_json()
        data_30 = resp_30.get_json()
        assert data_30["estimated_cost_raw"] > data_10["estimated_cost_raw"]

    def test_num_questions_clamped_high(self, client):
        """Question count above 50 should be clamped."""
        resp = client.get("/api/estimate-cost?provider=gemini&num_questions=100")
        assert resp.status_code == 200
        data = resp.get_json()
        # Should use max 50 questions
        resp_50 = client.get("/api/estimate-cost?provider=gemini&num_questions=50")
        data_50 = resp_50.get_json()
        assert data["estimated_cost_raw"] == data_50["estimated_cost_raw"]

    def test_num_questions_clamped_low(self, client):
        """Question count below 1 should be clamped to 1."""
        resp = client.get("/api/estimate-cost?provider=gemini&num_questions=0")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["estimated_tokens"] > 0

    def test_invalid_num_questions_handled(self, client):
        """Non-numeric num_questions should not crash."""
        resp = client.get("/api/estimate-cost?num_questions=abc")
        assert resp.status_code == 200

    def test_missing_params_uses_defaults(self, client):
        """No query params should use defaults and succeed."""
        resp = client.get("/api/estimate-cost")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "estimated_cost" in data

    def test_unknown_provider_handled(self, client):
        """Unknown provider name should not crash."""
        resp = client.get("/api/estimate-cost?provider=nonexistent")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "estimated_cost" in data

    def test_requires_login(self, app_with_mock):
        """Endpoint should require authentication."""
        app, _ = app_with_mock
        with app.test_client() as c:
            resp = c.get("/api/estimate-cost")
            # Should redirect to login
            assert resp.status_code == 303

    def test_gemini_pro_higher_than_flash(self, client):
        """Gemini Pro should cost more than Gemini Flash."""
        resp_flash = client.get("/api/estimate-cost?provider=gemini&num_questions=10")
        resp_pro = client.get("/api/estimate-cost?provider=gemini-pro&num_questions=10")
        flash_cost = resp_flash.get_json()["estimated_cost_raw"]
        pro_cost = resp_pro.get_json()["estimated_cost_raw"]
        assert pro_cost > flash_cost


# ============================================================
# Template integration tests
# ============================================================


class TestCostEstimateOnForms:
    """Test that cost estimate elements appear on generation forms."""

    def test_quiz_generate_has_estimate_div(self, client):
        """Quiz generate form should contain the cost-estimate div."""
        resp = client.get("/classes/1/generate")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'id="cost-estimate"' in html
        assert "cost-estimate-box" in html

    def test_quiz_generate_has_estimate_script(self, client):
        """Quiz generate form should contain the estimate fetch script."""
        resp = client.get("/classes/1/generate")
        html = resp.data.decode()
        assert "/api/estimate-cost" in html

    def test_exit_ticket_has_estimate_div(self, client):
        """Exit ticket form should contain the cost-estimate div."""
        resp = client.get("/exit-ticket/generate")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'id="cost-estimate"' in html
        assert "cost-estimate-box" in html

    def test_exit_ticket_has_estimate_script(self, client):
        """Exit ticket form should contain the estimate fetch script."""
        resp = client.get("/exit-ticket/generate")
        html = resp.data.decode()
        assert "/api/estimate-cost" in html
