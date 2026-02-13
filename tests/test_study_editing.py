"""
Tests for BL-007: Study Material Inline Editing.

Tests the API endpoints for editing, deleting, and reordering study cards,
and verifies the detail template renders edit controls.
"""

import json
import os
import tempfile

import pytest

from src.database import Base, Class, StudyCard, StudySet, get_engine, get_session


@pytest.fixture
def app():
    """Create a Flask test app with a study set and cards."""
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
    session.flush()

    study_set = StudySet(
        class_id=cls.id,
        title="Test Flashcards",
        material_type="flashcard",
        status="generated",
        config=json.dumps({}),
    )
    session.add(study_set)
    session.flush()

    # Add three cards
    for i, (front, back) in enumerate(
        [
            ("Term A", "Definition A"),
            ("Term B", "Definition B"),
            ("Term C", "Definition C"),
        ]
    ):
        card = StudyCard(
            study_set_id=study_set.id,
            card_type="flashcard",
            sort_order=i,
            front=front,
            back=back,
            data=json.dumps({"tags": ["science"]}),
        )
        session.add(card)

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

    flask_app.config["WTF_CSRF_ENABLED"] = False

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
    with c.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "teacher"
    return c


@pytest.fixture
def vocab_app():
    """Create a Flask test app with vocabulary study set."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session = get_session(engine)

    cls = Class(
        name="Vocab Class",
        grade_level="8th Grade",
        subject="English",
        standards=json.dumps([]),
        config=json.dumps({}),
    )
    session.add(cls)
    session.flush()

    study_set = StudySet(
        class_id=cls.id,
        title="Vocab Set",
        material_type="vocabulary",
        status="generated",
        config=json.dumps({}),
    )
    session.add(study_set)
    session.flush()

    for i, (front, back) in enumerate(
        [
            ("Photosynthesis", "Process by which plants make food"),
            ("Mitosis", "Cell division process"),
        ]
    ):
        card = StudyCard(
            study_set_id=study_set.id,
            card_type="term",
            sort_order=i,
            front=front,
            back=back,
            data=json.dumps({"example": "Example " + str(i), "part_of_speech": "noun"}),
        )
        session.add(card)

    session.commit()
    session.close()
    engine.dispose()

    from src.web.app import create_app

    test_config = {
        "paths": {"database_file": db_path},
        "llm": {"provider": "mock"},
        "generation": {"default_grade_level": "8th Grade"},
    }
    flask_app = create_app(test_config)
    flask_app.config["TESTING"] = True

    flask_app.config["WTF_CSRF_ENABLED"] = False

    yield flask_app

    flask_app.config["DB_ENGINE"].dispose()
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass


@pytest.fixture
def vocab_client(vocab_app):
    """Logged-in client for vocab app."""
    c = vocab_app.test_client()
    with c.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "teacher"
    return c


def _get_card_ids(app):
    """Helper to get card IDs from the database."""
    engine = app.config["DB_ENGINE"]
    session = get_session(engine)
    cards = session.query(StudyCard).order_by(StudyCard.sort_order).all()
    ids = [c.id for c in cards]
    session.close()
    return ids


def _get_study_set_id(app):
    """Helper to get the study set ID."""
    engine = app.config["DB_ENGINE"]
    session = get_session(engine)
    ss = session.query(StudySet).first()
    sid = ss.id
    session.close()
    return sid


# --- API: Update Card ---


class TestUpdateCard:
    def test_update_front_and_back(self, app, client):
        card_ids = _get_card_ids(app)
        resp = client.put(
            f"/api/study-cards/{card_ids[0]}",
            json={"front": "Updated Term", "back": "Updated Def"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["card"]["front"] == "Updated Term"
        assert data["card"]["back"] == "Updated Def"

    def test_update_front_only(self, app, client):
        card_ids = _get_card_ids(app)
        resp = client.put(
            f"/api/study-cards/{card_ids[1]}",
            json={"front": "New Front Only"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["card"]["front"] == "New Front Only"

    def test_update_persists(self, app, client):
        card_ids = _get_card_ids(app)
        client.put(
            f"/api/study-cards/{card_ids[0]}",
            json={"front": "Persisted Term"},
        )
        # Verify in DB
        engine = app.config["DB_ENGINE"]
        session = get_session(engine)
        card = session.query(StudyCard).filter_by(id=card_ids[0]).first()
        assert card.front == "Persisted Term"
        session.close()

    def test_update_data_field(self, app, client):
        card_ids = _get_card_ids(app)
        resp = client.put(
            f"/api/study-cards/{card_ids[0]}",
            json={"data": {"tags": ["updated"]}},
        )
        assert resp.status_code == 200
        # Verify in DB
        engine = app.config["DB_ENGINE"]
        session = get_session(engine)
        card = session.query(StudyCard).filter_by(id=card_ids[0]).first()
        parsed = json.loads(card.data)
        assert parsed["tags"] == ["updated"]
        session.close()

    def test_update_nonexistent_card(self, client):
        resp = client.put("/api/study-cards/99999", json={"front": "x"})
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["ok"] is False


# --- API: Delete Card ---


class TestDeleteCard:
    def test_delete_card(self, app, client):
        card_ids = _get_card_ids(app)
        resp = client.delete(f"/api/study-cards/{card_ids[0]}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

        # Verify removed from DB
        engine = app.config["DB_ENGINE"]
        session = get_session(engine)
        remaining = session.query(StudyCard).all()
        assert len(remaining) == 2
        session.close()

    def test_delete_nonexistent_card(self, client):
        resp = client.delete("/api/study-cards/99999")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["ok"] is False

    def test_delete_reduces_count(self, app, client):
        card_ids = _get_card_ids(app)
        for cid in card_ids:
            client.delete(f"/api/study-cards/{cid}")
        engine = app.config["DB_ENGINE"]
        session = get_session(engine)
        remaining = session.query(StudyCard).all()
        assert len(remaining) == 0
        session.close()


# --- API: Reorder Cards ---


class TestReorderCards:
    def test_reorder_cards(self, app, client):
        card_ids = _get_card_ids(app)
        study_set_id = _get_study_set_id(app)
        # Reverse order
        reversed_ids = list(reversed(card_ids))
        resp = client.post(
            f"/api/study-sets/{study_set_id}/reorder",
            json={"card_ids": reversed_ids},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

        # Verify sort_order in DB
        engine = app.config["DB_ENGINE"]
        session = get_session(engine)
        cards = session.query(StudyCard).order_by(StudyCard.sort_order).all()
        assert [c.id for c in cards] == reversed_ids
        session.close()

    def test_reorder_nonexistent_set(self, client):
        resp = client.post(
            "/api/study-sets/99999/reorder",
            json={"card_ids": [1, 2, 3]},
        )
        assert resp.status_code == 404

    def test_reorder_empty_ids(self, app, client):
        study_set_id = _get_study_set_id(app)
        resp = client.post(
            f"/api/study-sets/{study_set_id}/reorder",
            json={"card_ids": []},
        )
        assert resp.status_code == 400


# --- Detail Page Rendering ---


class TestDetailPageRendering:
    def test_detail_has_edit_buttons(self, app, client):
        study_set_id = _get_study_set_id(app)
        resp = client.get(f"/study/{study_set_id}")
        html = resp.data.decode()
        assert "card-edit-btn" in html
        assert "card-delete-btn" in html
        assert "card-move-up" in html
        assert "card-move-down" in html

    def test_detail_has_edit_form(self, app, client):
        study_set_id = _get_study_set_id(app)
        resp = client.get(f"/study/{study_set_id}")
        html = resp.data.decode()
        assert "edit-front" in html
        assert "edit-back" in html
        assert "edit-save-btn" in html

    def test_detail_has_study_set_id(self, app, client):
        study_set_id = _get_study_set_id(app)
        resp = client.get(f"/study/{study_set_id}")
        html = resp.data.decode()
        assert f'data-study-set-id="{study_set_id}"' in html

    def test_detail_loads_study_edit_js(self, app, client):
        study_set_id = _get_study_set_id(app)
        resp = client.get(f"/study/{study_set_id}")
        html = resp.data.decode()
        assert "study_edit.js" in html

    def test_vocab_has_actions_column(self, vocab_app, vocab_client):
        study_set_id = _get_study_set_id(vocab_app)
        resp = vocab_client.get(f"/study/{study_set_id}")
        html = resp.data.decode()
        assert "Actions" in html
        assert "vocab-edit-row" in html

    def test_detail_has_card_ids(self, app, client):
        study_set_id = _get_study_set_id(app)
        card_ids = _get_card_ids(app)
        resp = client.get(f"/study/{study_set_id}")
        html = resp.data.decode()
        for cid in card_ids:
            assert f'data-card-id="{cid}"' in html
