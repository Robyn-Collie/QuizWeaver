"""
Tests for BL-006: Cost Tracking Improvements.

Verifies budget tracking, monthly totals, budget checking, and
the improved cost tracking UI (budget bar, daily chart, provider bars).
"""

import json
import os
import tempfile
from datetime import datetime

import pytest

from src.cost_tracking import (
    check_budget,
    get_monthly_total,
)
from src.database import Base, Class, get_engine, get_session

# --- Unit tests for cost_tracking functions ---


class TestGetMonthlyTotal:
    """Test the get_monthly_total function."""

    def test_empty_log(self, tmp_path):
        """Empty log returns zeros."""
        log_file = str(tmp_path / "costs.log")
        result = get_monthly_total(log_file)
        assert result["calls"] == 0
        assert result["cost"] == 0.0

    def test_filters_by_current_month(self, tmp_path):
        """Only counts entries from the current month."""
        log_file = str(tmp_path / "costs.log")
        today = datetime.now()
        # Write current month entry
        ts = today.strftime("%Y-%m-%dT10:00:00")
        with open(log_file, "w") as f:
            f.write(f"{ts} | gemini | flash | 100 | 50 | $0.0010\n")
            f.write("2025-01-15T10:00:00 | gemini | flash | 200 | 100 | $0.0020\n")
        result = get_monthly_total(log_file, today.year, today.month)
        assert result["calls"] == 1
        assert abs(result["cost"] - 0.0010) < 0.0001

    def test_sums_multiple_entries(self, tmp_path):
        """Sums all entries for the month."""
        log_file = str(tmp_path / "costs.log")
        today = datetime.now()
        prefix = today.strftime("%Y-%m")
        with open(log_file, "w") as f:
            f.write(f"{prefix}-01T10:00:00 | gemini | flash | 100 | 50 | $0.0010\n")
            f.write(f"{prefix}-15T14:00:00 | gemini | flash | 200 | 100 | $0.0020\n")
            f.write(f"{prefix}-20T09:00:00 | openai | gpt-4 | 300 | 150 | $0.0500\n")
        result = get_monthly_total(log_file, today.year, today.month)
        assert result["calls"] == 3
        assert abs(result["cost"] - 0.0530) < 0.0001


class TestCheckBudget:
    """Test the check_budget function."""

    def test_no_budget_set(self, tmp_path):
        """No budget returns enabled=False."""
        log_file = str(tmp_path / "costs.log")
        config = {"llm": {}}
        result = check_budget(config, log_file)
        assert result["enabled"] is False
        assert result["exceeded"] is False

    def test_budget_not_exceeded(self, tmp_path):
        """Under-budget returns exceeded=False."""
        log_file = str(tmp_path / "costs.log")
        today = datetime.now()
        ts = today.strftime("%Y-%m-%dT10:00:00")
        with open(log_file, "w") as f:
            f.write(f"{ts} | gemini | flash | 100 | 50 | $1.0000\n")
        config = {"llm": {"monthly_budget": 5.00}}
        result = check_budget(config, log_file)
        assert result["enabled"] is True
        assert result["exceeded"] is False
        assert result["warning"] is False
        assert abs(result["spent"] - 1.0) < 0.01
        assert abs(result["remaining"] - 4.0) < 0.01
        assert abs(result["percent_used"] - 20.0) < 1.0

    def test_budget_warning_at_80_percent(self, tmp_path):
        """Warning triggers at 80% of budget."""
        log_file = str(tmp_path / "costs.log")
        today = datetime.now()
        ts = today.strftime("%Y-%m-%dT10:00:00")
        with open(log_file, "w") as f:
            f.write(f"{ts} | gemini | flash | 100 | 50 | $4.1000\n")
        config = {"llm": {"monthly_budget": 5.00}}
        result = check_budget(config, log_file)
        assert result["warning"] is True
        assert result["exceeded"] is False

    def test_budget_exceeded(self, tmp_path):
        """Budget exceeded returns exceeded=True."""
        log_file = str(tmp_path / "costs.log")
        today = datetime.now()
        ts = today.strftime("%Y-%m-%dT10:00:00")
        with open(log_file, "w") as f:
            f.write(f"{ts} | gemini | flash | 100 | 50 | $5.5000\n")
        config = {"llm": {"monthly_budget": 5.00}}
        result = check_budget(config, log_file)
        assert result["exceeded"] is True
        assert result["remaining"] == 0.0


# --- Integration tests for the web UI ---


@pytest.fixture
def app():
    """Create a Flask test app."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    cls = Class(
        name="Test Class",
        grade_level="7th Grade",
        subject="Science",
        standards=json.dumps([]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.commit()
    session.close()
    engine.dispose()

    from src.web.app import create_app

    test_config = {
        "paths": {"database_file": db_path},
        "llm": {"provider": "mock"},
        "generation": {"default_grade_level": "7th Grade"},
    }
    flask_app = create_app(test_config)
    flask_app.config["TESTING"] = True

    yield flask_app

    flask_app.config["DB_ENGINE"].dispose()
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


@pytest.fixture
def client(app):
    """Create a logged-in test client."""
    c = app.test_client()
    c.post("/login", data={"username": "teacher", "password": "quizweaver"})
    return c


class TestCostsPageUI:
    """Test the costs page renders correctly."""

    def test_costs_page_loads(self, client):
        """Costs page returns 200."""
        response = client.get("/costs")
        assert response.status_code == 200

    def test_costs_page_has_budget_section(self, client):
        """Costs page has the Monthly Budget section."""
        response = client.get("/costs")
        html = response.data.decode()
        assert "Monthly Budget" in html
        assert "monthly_budget" in html

    def test_costs_page_has_this_month(self, client):
        """Costs page has the This Month section."""
        response = client.get("/costs")
        html = response.data.decode()
        assert "This Month" in html

    def test_costs_page_has_budget_form(self, client):
        """Costs page has a form to set the budget."""
        response = client.get("/costs")
        html = response.data.decode()
        assert "Set Budget" in html
        assert "Monthly Limit" in html

    def test_set_budget_via_post(self, client):
        """Setting budget via POST updates config and redirects."""
        response = client.post("/costs", data={"monthly_budget": "5.00"})
        assert response.status_code == 303

        # Verify the page now shows the budget
        response = client.get("/costs")
        html = response.data.decode()
        assert "budget-bar-container" in html
