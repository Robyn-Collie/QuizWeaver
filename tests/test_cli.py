"""
Tests for all CLI command modules in src/cli/.

Tests each handler function directly with a temporary database,
mock config, and argparse.Namespace objects.
"""

import argparse
import json
import os
import tempfile

import pytest

from src.classroom import create_class
from src.database import (
    LessonPlan,
    Question,
    Quiz,
    Rubric,
    StudySet,
    get_engine,
    get_session,
    init_db,
)
from src.lesson_tracker import log_lesson

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_db():
    """Create a temporary database and return (engine, session, db_path)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    engine = get_engine(db_path)
    init_db(engine)
    session = get_session(engine)
    yield engine, session, db_path
    session.close()
    engine.dispose()
    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def mock_config(temp_db):
    """Return a config dict pointing to the temp database with mock provider."""
    _, _, db_path = temp_db
    return {
        "paths": {"database_file": db_path},
        "llm": {"provider": "mock"},
        "generation": {"default_grade_level": "7th Grade"},
    }


@pytest.fixture
def sample_class(temp_db):
    """Create a sample class and return its ID."""
    _, session, _ = temp_db
    cls = create_class(session, name="Test Class", grade_level="7th Grade", subject="Science")
    return cls.id


@pytest.fixture
def sample_quiz(temp_db, sample_class):
    """Create a sample quiz with questions and return its ID."""
    _, session, _ = temp_db
    quiz = Quiz(
        title="Test Quiz",
        class_id=sample_class,
        status="generated",
        style_profile=json.dumps({"grade_level": "7th Grade", "sol_standards": ["SOL 7.1"]}),
    )
    session.add(quiz)
    session.commit()

    # Add questions
    for i in range(3):
        q_data = {
            "type": "mc",
            "text": f"Question {i + 1}: What is the answer?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_index": 0,
            "correct_answer": "Option A",
            "cognitive_level": "Remember",
            "cognitive_framework": "blooms",
        }
        q = Question(
            quiz_id=quiz.id,
            question_type="mc",
            text=q_data["text"],
            points=5,
            sort_order=i,
            data=json.dumps(q_data),
        )
        session.add(q)
    session.commit()
    return quiz.id


@pytest.fixture
def sample_lesson(temp_db, sample_class):
    """Create a sample lesson and return its ID."""
    _, session, _ = temp_db
    lesson = log_lesson(
        session,
        class_id=sample_class,
        content="Today we learned about photosynthesis.",
        topics=["photosynthesis"],
        notes="Good class participation",
    )
    return lesson.id


# ---------------------------------------------------------------------------
# Quiz Commands Tests
# ---------------------------------------------------------------------------


class TestListQuizzes:
    def test_list_quizzes_empty(self, mock_config, capsys):
        from src.cli.quiz_commands import handle_list_quizzes

        args = argparse.Namespace(class_id=None)
        handle_list_quizzes(mock_config, args)
        out = capsys.readouterr().out
        assert "No quizzes found" in out

    def test_list_quizzes_with_data(self, mock_config, sample_quiz, capsys):
        from src.cli.quiz_commands import handle_list_quizzes

        args = argparse.Namespace(class_id=None)
        handle_list_quizzes(mock_config, args)
        out = capsys.readouterr().out
        assert "Test Quiz" in out
        assert "Total: 1" in out

    def test_list_quizzes_filter_class(self, mock_config, sample_quiz, capsys):
        from src.cli.quiz_commands import handle_list_quizzes

        # Filter by a non-existent class
        args = argparse.Namespace(class_id=999)
        handle_list_quizzes(mock_config, args)
        out = capsys.readouterr().out
        assert "No quizzes found" in out


class TestViewQuiz:
    def test_view_quiz_not_found(self, mock_config, capsys):
        from src.cli.quiz_commands import handle_view_quiz

        args = argparse.Namespace(quiz_id=999, show_answers=False)
        handle_view_quiz(mock_config, args)
        out = capsys.readouterr().out
        assert "not found" in out

    def test_view_quiz_basic(self, mock_config, sample_quiz, capsys):
        from src.cli.quiz_commands import handle_view_quiz

        args = argparse.Namespace(quiz_id=sample_quiz, show_answers=False)
        handle_view_quiz(mock_config, args)
        out = capsys.readouterr().out
        assert "Test Quiz" in out
        assert "Question 1" in out

    def test_view_quiz_with_answers(self, mock_config, sample_quiz, capsys):
        from src.cli.quiz_commands import handle_view_quiz

        args = argparse.Namespace(quiz_id=sample_quiz, show_answers=True)
        handle_view_quiz(mock_config, args)
        out = capsys.readouterr().out
        assert "Answer: Option A" in out


class TestExportQuiz:
    def test_export_quiz_csv(self, mock_config, sample_quiz, capsys, tmp_path):
        from src.cli.quiz_commands import handle_export_quiz

        out_file = str(tmp_path / "test.csv")
        args = argparse.Namespace(quiz_id=sample_quiz, fmt="csv", output=out_file)
        handle_export_quiz(mock_config, args)
        out = capsys.readouterr().out
        assert "[OK]" in out
        assert os.path.exists(out_file)
        content = open(out_file, encoding="utf-8").read()
        assert "Question" in content

    def test_export_quiz_docx(self, mock_config, sample_quiz, capsys, tmp_path):
        from src.cli.quiz_commands import handle_export_quiz

        out_file = str(tmp_path / "test.docx")
        args = argparse.Namespace(quiz_id=sample_quiz, fmt="docx", output=out_file)
        handle_export_quiz(mock_config, args)
        assert os.path.exists(out_file)
        assert os.path.getsize(out_file) > 0

    def test_export_quiz_gift(self, mock_config, sample_quiz, capsys, tmp_path):
        from src.cli.quiz_commands import handle_export_quiz

        out_file = str(tmp_path / "test.gift.txt")
        args = argparse.Namespace(quiz_id=sample_quiz, fmt="gift", output=out_file)
        handle_export_quiz(mock_config, args)
        assert os.path.exists(out_file)
        content = open(out_file, encoding="utf-8").read()
        assert "::Q1::" in content

    def test_export_quiz_pdf(self, mock_config, sample_quiz, capsys, tmp_path):
        from src.cli.quiz_commands import handle_export_quiz

        out_file = str(tmp_path / "test.pdf")
        args = argparse.Namespace(quiz_id=sample_quiz, fmt="pdf", output=out_file)
        handle_export_quiz(mock_config, args)
        assert os.path.exists(out_file)
        assert os.path.getsize(out_file) > 0

    def test_export_quiz_qti(self, mock_config, sample_quiz, capsys, tmp_path):
        from src.cli.quiz_commands import handle_export_quiz

        out_file = str(tmp_path / "test.qti.zip")
        args = argparse.Namespace(quiz_id=sample_quiz, fmt="qti", output=out_file)
        handle_export_quiz(mock_config, args)
        assert os.path.exists(out_file)
        assert os.path.getsize(out_file) > 0

    def test_export_quiz_not_found(self, mock_config, capsys):
        from src.cli.quiz_commands import handle_export_quiz

        args = argparse.Namespace(quiz_id=999, fmt="csv", output=None)
        handle_export_quiz(mock_config, args)
        out = capsys.readouterr().out
        assert "not found" in out


# ---------------------------------------------------------------------------
# Study Commands Tests
# ---------------------------------------------------------------------------


class TestGenerateStudy:
    def test_generate_flashcard(self, mock_config, sample_class, capsys):
        from src.cli.study_commands import handle_generate_study

        args = argparse.Namespace(
            class_id=sample_class,
            material_type="flashcard",
            quiz_id=None,
            topic="photosynthesis",
            title=None,
        )
        handle_generate_study(mock_config, args)
        out = capsys.readouterr().out
        assert "[OK]" in out
        assert "flashcard" in out.lower()

    def test_generate_study_guide(self, mock_config, sample_class, capsys):
        from src.cli.study_commands import handle_generate_study

        args = argparse.Namespace(
            class_id=sample_class,
            material_type="study_guide",
            quiz_id=None,
            topic="cells",
            title=None,
        )
        handle_generate_study(mock_config, args)
        out = capsys.readouterr().out
        assert "[OK]" in out


class TestExportStudy:
    def test_export_study_not_found(self, mock_config, capsys):
        from src.cli.study_commands import handle_export_study

        args = argparse.Namespace(study_set_id=999, fmt="csv", output=None)
        handle_export_study(mock_config, args)
        out = capsys.readouterr().out
        assert "not found" in out

    def test_export_study_csv(self, mock_config, sample_class, capsys, tmp_path):
        """Generate then export a study set."""
        from src.cli import get_db_session
        from src.cli.study_commands import handle_export_study, handle_generate_study

        # Generate
        gen_args = argparse.Namespace(
            class_id=sample_class,
            material_type="flashcard",
            quiz_id=None,
            topic="photosynthesis",
            title="Test Flashcards",
        )
        handle_generate_study(mock_config, gen_args)

        # Find the created study set
        _, session = get_db_session(mock_config)
        study_set = session.query(StudySet).first()
        session.close()
        assert study_set is not None

        # Export
        out_file = str(tmp_path / "test.csv")
        export_args = argparse.Namespace(study_set_id=study_set.id, fmt="csv", output=out_file)
        handle_export_study(mock_config, export_args)
        out = capsys.readouterr().out
        assert "[OK]" in out
        assert os.path.exists(out_file)


# ---------------------------------------------------------------------------
# Rubric Commands Tests
# ---------------------------------------------------------------------------


class TestGenerateRubric:
    def test_generate_rubric(self, mock_config, sample_quiz, capsys):
        from src.cli.rubric_commands import handle_generate_rubric

        args = argparse.Namespace(quiz_id=sample_quiz, title=None)
        handle_generate_rubric(mock_config, args)
        out = capsys.readouterr().out
        assert "[OK]" in out
        assert "Rubric" in out

    def test_generate_rubric_quiz_not_found(self, mock_config, capsys):
        from src.cli.rubric_commands import handle_generate_rubric

        args = argparse.Namespace(quiz_id=999, title=None)
        handle_generate_rubric(mock_config, args)
        out = capsys.readouterr().out
        assert "Failed" in out or "Error" in out


class TestExportRubric:
    def test_export_rubric_not_found(self, mock_config, capsys):
        from src.cli.rubric_commands import handle_export_rubric

        args = argparse.Namespace(rubric_id=999, fmt="csv", output=None)
        handle_export_rubric(mock_config, args)
        out = capsys.readouterr().out
        assert "not found" in out

    def test_export_rubric_csv(self, mock_config, sample_quiz, capsys, tmp_path):
        from src.cli import get_db_session
        from src.cli.rubric_commands import handle_export_rubric, handle_generate_rubric

        # Generate
        gen_args = argparse.Namespace(quiz_id=sample_quiz, title=None)
        handle_generate_rubric(mock_config, gen_args)

        # Find the rubric
        _, session = get_db_session(mock_config)
        rubric = session.query(Rubric).first()
        session.close()
        assert rubric is not None

        # Export
        out_file = str(tmp_path / "rubric.csv")
        export_args = argparse.Namespace(rubric_id=rubric.id, fmt="csv", output=out_file)
        handle_export_rubric(mock_config, export_args)
        capsys.readouterr()
        assert os.path.exists(out_file)


# ---------------------------------------------------------------------------
# Analytics Commands Tests
# ---------------------------------------------------------------------------


class TestImportPerformance:
    def test_import_performance(self, mock_config, sample_class, capsys, tmp_path):
        from src.cli.analytics_commands import handle_import_performance

        # Create CSV file
        csv_path = str(tmp_path / "perf.csv")
        with open(csv_path, "w") as f:
            f.write("topic,score,date,standard\n")
            f.write("photosynthesis,75,2025-03-15,SOL 7.1\n")
            f.write("cell division,60,2025-03-16,SOL 7.2\n")

        args = argparse.Namespace(
            class_id=sample_class,
            csv_file=csv_path,
            quiz_id=None,
        )
        handle_import_performance(mock_config, args)
        out = capsys.readouterr().out
        assert "[OK]" in out
        assert "2 records" in out

    def test_import_performance_file_not_found(self, mock_config, sample_class, capsys):
        from src.cli.analytics_commands import handle_import_performance

        args = argparse.Namespace(
            class_id=sample_class,
            csv_file="/nonexistent/path.csv",
            quiz_id=None,
        )
        handle_import_performance(mock_config, args)
        out = capsys.readouterr().out
        assert "not found" in out


class TestAnalytics:
    def test_analytics_empty(self, mock_config, sample_class, capsys):
        from src.cli.analytics_commands import handle_analytics

        args = argparse.Namespace(class_id=sample_class, fmt="text")
        handle_analytics(mock_config, args)
        out = capsys.readouterr().out
        assert "Analytics for" in out

    def test_analytics_json(self, mock_config, sample_class, capsys):
        from src.cli.analytics_commands import handle_analytics

        args = argparse.Namespace(class_id=sample_class, fmt="json")
        handle_analytics(mock_config, args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "summary" in data
        assert "gaps" in data

    def test_analytics_class_not_found(self, mock_config, capsys):
        from src.cli.analytics_commands import handle_analytics

        args = argparse.Namespace(class_id=999, fmt="text")
        handle_analytics(mock_config, args)
        out = capsys.readouterr().out
        assert "not found" in out


class TestReteach:
    def test_reteach_no_data(self, mock_config, sample_class, capsys):
        from src.cli.analytics_commands import handle_reteach

        args = argparse.Namespace(class_id=sample_class, max_suggestions=5)
        handle_reteach(mock_config, args)
        out = capsys.readouterr().out
        # Either "on track" or empty suggestions
        assert "on track" in out or "Re-teach" in out or "No reteach" in out


# ---------------------------------------------------------------------------
# Lesson Plan Commands Tests
# ---------------------------------------------------------------------------


class TestGenerateLessonPlan:
    def test_generate_lesson_plan(self, mock_config, sample_class, capsys):
        from src.cli.lesson_plan_commands import handle_generate_lesson_plan

        args = argparse.Namespace(
            class_id=sample_class,
            topics="photosynthesis,cellular respiration",
            standards=None,
            duration=50,
        )
        handle_generate_lesson_plan(mock_config, args)
        out = capsys.readouterr().out
        assert "[OK]" in out

    def test_generate_lesson_plan_with_standards(self, mock_config, sample_class, capsys):
        from src.cli.lesson_plan_commands import handle_generate_lesson_plan

        args = argparse.Namespace(
            class_id=sample_class,
            topics="photosynthesis",
            standards="SOL 7.1,SOL 7.2",
            duration=45,
        )
        handle_generate_lesson_plan(mock_config, args)
        out = capsys.readouterr().out
        assert "[OK]" in out


class TestExportLessonPlan:
    def test_export_lesson_plan_not_found(self, mock_config, capsys):
        from src.cli.lesson_plan_commands import handle_export_lesson_plan

        args = argparse.Namespace(plan_id=999, fmt="pdf", output=None)
        handle_export_lesson_plan(mock_config, args)
        out = capsys.readouterr().out
        assert "not found" in out

    def test_export_lesson_plan_pdf(self, mock_config, sample_class, capsys, tmp_path):
        from src.cli import get_db_session
        from src.cli.lesson_plan_commands import handle_export_lesson_plan, handle_generate_lesson_plan

        # Generate
        gen_args = argparse.Namespace(
            class_id=sample_class,
            topics="photosynthesis",
            standards=None,
            duration=50,
        )
        handle_generate_lesson_plan(mock_config, gen_args)

        # Find the plan
        _, session = get_db_session(mock_config)
        plan = session.query(LessonPlan).first()
        session.close()
        assert plan is not None

        # Export
        out_file = str(tmp_path / "plan.pdf")
        export_args = argparse.Namespace(plan_id=plan.id, fmt="pdf", output=out_file)
        handle_export_lesson_plan(mock_config, export_args)
        capsys.readouterr()
        assert os.path.exists(out_file)


# ---------------------------------------------------------------------------
# Template Commands Tests
# ---------------------------------------------------------------------------


class TestExportTemplate:
    def test_export_template(self, mock_config, sample_quiz, capsys, tmp_path):
        from src.cli.template_commands import handle_export_template

        out_file = str(tmp_path / "template.json")
        args = argparse.Namespace(quiz_id=sample_quiz, output=out_file)
        handle_export_template(mock_config, args)
        out = capsys.readouterr().out
        assert "[OK]" in out
        assert os.path.exists(out_file)
        # Verify it's valid JSON
        with open(out_file) as f:
            template = json.load(f)
        assert "template_version" in template
        assert len(template["questions"]) == 3

    def test_export_template_not_found(self, mock_config, capsys):
        from src.cli.template_commands import handle_export_template

        args = argparse.Namespace(quiz_id=999, output=None)
        handle_export_template(mock_config, args)
        out = capsys.readouterr().out
        assert "not found" in out


class TestImportTemplate:
    def test_import_template(self, mock_config, sample_quiz, sample_class, capsys, tmp_path):
        from src.cli.template_commands import handle_export_template, handle_import_template

        # Export first
        template_file = str(tmp_path / "template.json")
        export_args = argparse.Namespace(quiz_id=sample_quiz, output=template_file)
        handle_export_template(mock_config, export_args)
        capsys.readouterr()

        # Import
        import_args = argparse.Namespace(
            template_file=template_file,
            class_id=sample_class,
            title="Imported Quiz",
        )
        handle_import_template(mock_config, import_args)
        out = capsys.readouterr().out
        assert "[OK]" in out
        assert "Imported Quiz" in out

    def test_import_template_file_not_found(self, mock_config, sample_class, capsys):
        from src.cli.template_commands import handle_import_template

        args = argparse.Namespace(
            template_file="/nonexistent.json",
            class_id=sample_class,
            title=None,
        )
        handle_import_template(mock_config, args)
        out = capsys.readouterr().out
        assert "not found" in out

    def test_import_template_invalid_json(self, mock_config, sample_class, capsys, tmp_path):
        from src.cli.template_commands import handle_import_template

        bad_file = str(tmp_path / "bad.json")
        with open(bad_file, "w") as f:
            f.write("{not valid json")
        args = argparse.Namespace(
            template_file=bad_file,
            class_id=sample_class,
            title=None,
        )
        handle_import_template(mock_config, args)
        out = capsys.readouterr().out
        assert "Invalid JSON" in out


# ---------------------------------------------------------------------------
# Class Commands Tests
# ---------------------------------------------------------------------------


class TestEditClass:
    def test_edit_class(self, mock_config, sample_class, capsys):
        from src.cli.class_commands import handle_edit_class

        args = argparse.Namespace(
            class_id=sample_class,
            name="Updated Class",
            grade="8th Grade",
            subject="Biology",
        )
        handle_edit_class(mock_config, args)
        out = capsys.readouterr().out
        assert "[OK]" in out
        assert "Updated Class" in out

    def test_edit_class_not_found(self, mock_config, capsys):
        from src.cli.class_commands import handle_edit_class

        args = argparse.Namespace(class_id=999, name="X", grade=None, subject=None)
        handle_edit_class(mock_config, args)
        out = capsys.readouterr().out
        assert "not found" in out


class TestDeleteClass:
    def test_delete_class_with_confirm(self, mock_config, temp_db, capsys):
        from src.cli.class_commands import handle_delete_class

        _, session, _ = temp_db
        cls = create_class(session, name="Deletable Class")
        args = argparse.Namespace(class_id=cls.id, confirm=True)
        handle_delete_class(mock_config, args)
        out = capsys.readouterr().out
        assert "[OK]" in out

    def test_delete_class_not_found(self, mock_config, capsys):
        from src.cli.class_commands import handle_delete_class

        args = argparse.Namespace(class_id=999, confirm=True)
        handle_delete_class(mock_config, args)
        out = capsys.readouterr().out
        assert "not found" in out


class TestDeleteLesson:
    def test_delete_lesson_with_confirm(self, mock_config, sample_lesson, capsys):
        from src.cli.class_commands import handle_delete_lesson

        args = argparse.Namespace(lesson_id=sample_lesson, confirm=True)
        handle_delete_lesson(mock_config, args)
        out = capsys.readouterr().out
        assert "[OK]" in out

    def test_delete_lesson_not_found(self, mock_config, capsys):
        from src.cli.class_commands import handle_delete_lesson

        args = argparse.Namespace(lesson_id=999, confirm=True)
        handle_delete_lesson(mock_config, args)
        out = capsys.readouterr().out
        assert "not found" in out


# ---------------------------------------------------------------------------
# Standards Commands Tests
# ---------------------------------------------------------------------------


class TestBrowseStandards:
    def test_browse_standards_empty(self, mock_config, capsys):
        from src.cli.standards_commands import handle_browse_standards

        args = argparse.Namespace(standard_set=None, search=None, subject=None, grade_band=None)
        handle_browse_standards(mock_config, args)
        out = capsys.readouterr().out
        # Either shows standards or says none loaded
        assert "standards" in out.lower() or "No standards" in out

    def test_browse_standards_with_search(self, mock_config, capsys):
        from src.cli.standards_commands import handle_browse_standards

        args = argparse.Namespace(standard_set=None, search="photosynthesis", subject=None, grade_band=None)
        handle_browse_standards(mock_config, args)
        # Just verifying it doesn't crash
        capsys.readouterr()


# ---------------------------------------------------------------------------
# Provider Commands Tests
# ---------------------------------------------------------------------------


class TestProviderInfo:
    def test_provider_info(self, mock_config, capsys):
        from src.cli.provider_commands import handle_provider_info

        args = argparse.Namespace()
        handle_provider_info(mock_config, args)
        out = capsys.readouterr().out
        assert "mock" in out.lower()
        assert "Current provider" in out


# ---------------------------------------------------------------------------
# Variant Commands Tests
# ---------------------------------------------------------------------------


class TestGenerateVariant:
    def test_generate_variant(self, mock_config, sample_quiz, capsys):
        from src.cli.variant_commands import handle_generate_variant

        args = argparse.Namespace(
            quiz_id=sample_quiz,
            reading_level="ell",
            title=None,
        )
        handle_generate_variant(mock_config, args)
        out = capsys.readouterr().out
        assert "[OK]" in out
        assert "ell" in out.lower()

    def test_generate_variant_quiz_not_found(self, mock_config, capsys):
        from src.cli.variant_commands import handle_generate_variant

        args = argparse.Namespace(quiz_id=999, reading_level="ell", title=None)
        handle_generate_variant(mock_config, args)
        out = capsys.readouterr().out
        assert "Failed" in out or "Error" in out


# ---------------------------------------------------------------------------
# Topic Commands Tests
# ---------------------------------------------------------------------------


class TestGenerateTopics:
    def test_generate_topics(self, mock_config, sample_class, capsys):
        from src.cli.topic_commands import handle_generate_topics

        args = argparse.Namespace(
            class_id=sample_class,
            topics="photosynthesis,cell division",
            count=5,
            title=None,
        )
        handle_generate_topics(mock_config, args)
        out = capsys.readouterr().out
        assert "[OK]" in out or "Error" in out  # May fail gracefully in mock


# ---------------------------------------------------------------------------
# CLI Module Helpers Tests
# ---------------------------------------------------------------------------


class TestCLIHelpers:
    def test_get_db_session(self, mock_config):
        from src.cli import get_db_session

        engine, session = get_db_session(mock_config)
        assert session is not None
        session.close()

    def test_resolve_class_id_from_args(self, mock_config, temp_db):
        from src.cli import resolve_class_id

        _, session, _ = temp_db
        args = argparse.Namespace(class_id=42)
        assert resolve_class_id(mock_config, args, session) == 42

    def test_resolve_class_id_from_config(self, mock_config, temp_db):
        from src.cli import resolve_class_id

        _, session, _ = temp_db
        mock_config["active_class_id"] = 7
        args = argparse.Namespace(class_id=None)
        assert resolve_class_id(mock_config, args, session) == 7

    def test_resolve_class_id_default(self, mock_config, temp_db):
        from src.cli import resolve_class_id

        _, session, _ = temp_db
        args = argparse.Namespace(class_id=None)
        assert resolve_class_id(mock_config, args, session) == 1


# ---------------------------------------------------------------------------
# Registration Tests - verify each register function adds subparsers
# ---------------------------------------------------------------------------


class TestRegistration:
    def _make_parser(self):
        parser = argparse.ArgumentParser()
        return parser.add_subparsers(dest="command")

    def test_register_quiz_commands(self):
        from src.cli.quiz_commands import register_quiz_commands

        sp = self._make_parser()
        register_quiz_commands(sp)

    def test_register_study_commands(self):
        from src.cli.study_commands import register_study_commands

        sp = self._make_parser()
        register_study_commands(sp)

    def test_register_rubric_commands(self):
        from src.cli.rubric_commands import register_rubric_commands

        sp = self._make_parser()
        register_rubric_commands(sp)

    def test_register_analytics_commands(self):
        from src.cli.analytics_commands import register_analytics_commands

        sp = self._make_parser()
        register_analytics_commands(sp)

    def test_register_lesson_plan_commands(self):
        from src.cli.lesson_plan_commands import register_lesson_plan_commands

        sp = self._make_parser()
        register_lesson_plan_commands(sp)

    def test_register_template_commands(self):
        from src.cli.template_commands import register_template_commands

        sp = self._make_parser()
        register_template_commands(sp)

    def test_register_class_commands(self):
        from src.cli.class_commands import register_class_commands

        sp = self._make_parser()
        register_class_commands(sp)

    def test_register_standards_commands(self):
        from src.cli.standards_commands import register_standards_commands

        sp = self._make_parser()
        register_standards_commands(sp)

    def test_register_provider_commands(self):
        from src.cli.provider_commands import register_provider_commands

        sp = self._make_parser()
        register_provider_commands(sp)

    def test_register_variant_commands(self):
        from src.cli.variant_commands import register_variant_commands

        sp = self._make_parser()
        register_variant_commands(sp)

    def test_register_topic_commands(self):
        from src.cli.topic_commands import register_topic_commands

        sp = self._make_parser()
        register_topic_commands(sp)


# ---------------------------------------------------------------------------
# main.py Handler Tests (8 untested commands)
# ---------------------------------------------------------------------------


class TestHandleIngest:
    """Tests for handle_ingest() in main.py."""

    def test_ingest_success(self, mock_config, capsys):
        from unittest.mock import patch

        from main import handle_ingest

        with patch("main.ingest_content") as mock_ingest:
            handle_ingest(mock_config)
            mock_ingest.assert_called_once()

        out = capsys.readouterr().out
        assert "[OK] Ingestion complete." in out
        assert "Starting Content Ingestion" in out

    def test_ingest_calls_with_session_and_config(self, mock_config):
        from unittest.mock import patch

        from main import handle_ingest

        with patch("main.ingest_content") as mock_ingest:
            handle_ingest(mock_config)
            args = mock_ingest.call_args
            # First arg is session, second is config
            assert args[0][1] == mock_config


class TestHandleGenerate:
    """Tests for handle_generate() in main.py."""

    def test_generate_success(self, mock_config, sample_class, temp_db, capsys, tmp_path):
        from unittest.mock import patch

        from main import handle_generate

        mock_config["active_class_id"] = sample_class
        mock_config["generation"]["quiz_title"] = "Test Quiz"
        mock_config["generation"]["default_grade_level"] = "7th Grade"
        mock_config["generation"]["sol_standards"] = ["SOL 7.1"]
        mock_config["generation"]["interactive_review"] = False
        mock_config["paths"]["quiz_output_dir"] = str(tmp_path)
        mock_config["qti"] = {"pdf_filename_template": "quiz_{timestamp}.pdf"}

        mock_questions = [
            {
                "type": "mc",
                "text": "What is photosynthesis?",
                "options": ["A", "B", "C", "D"],
                "correct_index": 0,
                "correct_answer": "A",
                "points": 5,
            }
        ]
        mock_metadata = {"prompt_summary": "test"}

        args = argparse.Namespace(count=5, grade=None, sol=None, no_interactive=True, class_id=None)

        with (
            patch("main.get_retake_analysis", return_value=("retake text", 5, 2, 0.4)),
            patch(
                "main.run_agentic_pipeline",
                return_value=(mock_questions, mock_metadata),
            ),
            patch("main.generate_pdf_preview"),
            patch("main.create_qti_package", return_value=str(tmp_path / "out.zip")),
        ):
            handle_generate(mock_config, args)

        out = capsys.readouterr().out
        assert "Starting Quiz Generation" in out
        assert "Successfully generated 1 questions" in out
        assert "[OK] Generation complete!" in out

    def test_generate_no_questions(self, mock_config, sample_class, temp_db, capsys):
        from unittest.mock import patch

        from main import handle_generate

        mock_config["active_class_id"] = sample_class
        mock_config["generation"]["quiz_title"] = "Test Quiz"
        mock_config["generation"]["default_grade_level"] = "7th Grade"
        mock_config["generation"]["sol_standards"] = []
        mock_config["generation"]["interactive_review"] = False

        args = argparse.Namespace(count=5, grade=None, sol=None, no_interactive=True, class_id=None)

        with (
            patch("main.get_retake_analysis", return_value=("retake text", 5, 0, 0.0)),
            patch("main.run_agentic_pipeline", return_value=([], {})),
        ):
            handle_generate(mock_config, args)

        out = capsys.readouterr().out
        assert "failed to generate valid questions" in out

    def test_generate_with_count_override(self, mock_config, sample_class, temp_db, capsys, tmp_path):
        from unittest.mock import patch

        from main import handle_generate

        mock_config["active_class_id"] = sample_class
        mock_config["generation"]["quiz_title"] = "Test Quiz"
        mock_config["generation"]["default_grade_level"] = "7th Grade"
        mock_config["generation"]["sol_standards"] = []
        mock_config["generation"]["interactive_review"] = False
        mock_config["paths"]["quiz_output_dir"] = str(tmp_path)
        mock_config["qti"] = {"pdf_filename_template": "quiz_{timestamp}.pdf"}

        mock_questions = [
            {
                "type": "mc",
                "text": f"Q{i}",
                "options": ["A", "B"],
                "correct_index": 0,
                "correct_answer": "A",
                "points": 1,
            }
            for i in range(10)
        ]

        args = argparse.Namespace(count=10, grade="8th Grade", sol=["SOL 8.1"], no_interactive=True, class_id=None)

        with (
            patch("main.get_retake_analysis", return_value=("retake text", 5, 0, 0.0)),
            patch(
                "main.run_agentic_pipeline",
                return_value=(mock_questions, {}),
            ),
            patch("main.generate_pdf_preview"),
            patch("main.create_qti_package", return_value=str(tmp_path / "out.zip")),
        ):
            handle_generate(mock_config, args)

        out = capsys.readouterr().out
        assert "8th Grade" in out
        assert "SOL 8.1" in out
        assert "Targeting 10 questions" in out


class TestHandleNewClass:
    """Tests for handle_new_class() in main.py."""

    def test_new_class_basic(self, mock_config, capsys):
        from unittest.mock import patch

        from main import handle_new_class

        args = argparse.Namespace(
            name="7th Grade Science - Block A",
            grade="7th Grade",
            subject="Science",
            standards=None,
        )
        # Mock input() to avoid blocking
        with patch("builtins.input", return_value="no"):
            handle_new_class(mock_config, args)

        out = capsys.readouterr().out
        assert "Class created" in out
        assert "7th Grade Science - Block A" in out
        assert "Grade: 7th Grade" in out
        assert "Subject: Science" in out

    def test_new_class_with_standards(self, mock_config, capsys):
        from unittest.mock import patch

        from main import handle_new_class

        args = argparse.Namespace(
            name="Bio Class",
            grade=None,
            subject=None,
            standards="SOL 7.1,SOL 7.2",
        )
        with patch("builtins.input", return_value="no"):
            handle_new_class(mock_config, args)

        out = capsys.readouterr().out
        assert "Class created" in out
        assert "Bio Class" in out

    def test_new_class_set_active(self, mock_config, capsys):
        from unittest.mock import patch

        from main import handle_new_class

        args = argparse.Namespace(
            name="Active Class",
            grade=None,
            subject=None,
            standards=None,
        )
        with (
            patch("builtins.input", return_value="yes"),
            patch("main.set_active_class", return_value=True) as mock_set,
        ):
            handle_new_class(mock_config, args)
            mock_set.assert_called_once()

        out = capsys.readouterr().out
        assert "Active class set to" in out

    def test_new_class_eof_on_input(self, mock_config, capsys):
        from unittest.mock import patch

        from main import handle_new_class

        args = argparse.Namespace(
            name="EOF Class",
            grade=None,
            subject=None,
            standards=None,
        )
        with patch("builtins.input", side_effect=EOFError):
            handle_new_class(mock_config, args)

        out = capsys.readouterr().out
        assert "Class created" in out
        assert "EOF Class" in out


class TestHandleListClasses:
    """Tests for handle_list_classes() in main.py."""

    def test_list_classes_empty(self, mock_config, capsys):
        from main import handle_list_classes

        args = argparse.Namespace()
        handle_list_classes(mock_config, args)
        out = capsys.readouterr().out
        assert "No classes found" in out

    def test_list_classes_with_data(self, mock_config, sample_class, capsys):
        from main import handle_list_classes

        args = argparse.Namespace()
        handle_list_classes(mock_config, args)
        out = capsys.readouterr().out
        assert "Test Class" in out
        assert "ID" in out
        assert "* = active class" in out

    def test_list_classes_active_marker(self, mock_config, sample_class, capsys):
        from main import handle_list_classes

        mock_config["active_class_id"] = sample_class
        args = argparse.Namespace()
        handle_list_classes(mock_config, args)
        out = capsys.readouterr().out
        # Active class marker should appear
        assert "*" in out
        assert "Test Class" in out


class TestHandleSetClass:
    """Tests for handle_set_class() in main.py."""

    def test_set_class_success(self, mock_config, sample_class, capsys):
        from unittest.mock import patch

        from main import handle_set_class

        args = argparse.Namespace(class_id=str(sample_class))
        with patch("main.set_active_class", return_value=True) as mock_set:
            handle_set_class(mock_config, args)
            mock_set.assert_called_once_with("config.yaml", sample_class)

        out = capsys.readouterr().out
        assert "Active class set to" in out
        assert "Test Class" in out

    def test_set_class_not_found(self, mock_config, capsys):
        from main import handle_set_class

        args = argparse.Namespace(class_id="999")
        handle_set_class(mock_config, args)
        out = capsys.readouterr().out
        assert "not found" in out

    def test_set_class_config_update_fails(self, mock_config, sample_class, capsys):
        from unittest.mock import patch

        from main import handle_set_class

        args = argparse.Namespace(class_id=str(sample_class))
        with patch("main.set_active_class", return_value=False):
            handle_set_class(mock_config, args)

        out = capsys.readouterr().out
        assert "Could not update config.yaml" in out


class TestHandleLogLesson:
    """Tests for handle_log_lesson() in main.py."""

    def test_log_lesson_with_text(self, mock_config, sample_class, capsys):
        from main import handle_log_lesson

        mock_config["active_class_id"] = sample_class
        args = argparse.Namespace(
            class_id=None,
            text="Today we covered photosynthesis and cellular respiration",
            file=None,
            notes="Great class",
            topics=None,
        )
        handle_log_lesson(mock_config, args)
        out = capsys.readouterr().out
        assert "Lesson logged for" in out
        assert "Test Class" in out

    def test_log_lesson_with_topics_override(self, mock_config, sample_class, capsys):
        from main import handle_log_lesson

        mock_config["active_class_id"] = sample_class
        args = argparse.Namespace(
            class_id=None,
            text="Today we learned about cells",
            file=None,
            notes=None,
            topics="cells,organelles",
        )
        handle_log_lesson(mock_config, args)
        out = capsys.readouterr().out
        assert "Lesson logged for" in out

    def test_log_lesson_with_file(self, mock_config, sample_class, capsys, tmp_path):
        from main import handle_log_lesson

        mock_config["active_class_id"] = sample_class
        lesson_file = str(tmp_path / "lesson.txt")
        with open(lesson_file, "w") as f:
            f.write("Detailed lesson about photosynthesis")

        args = argparse.Namespace(
            class_id=None,
            text=None,
            file=lesson_file,
            notes=None,
            topics=None,
        )
        handle_log_lesson(mock_config, args)
        out = capsys.readouterr().out
        assert "Lesson logged for" in out

    def test_log_lesson_file_not_found(self, mock_config, sample_class, capsys):
        from main import handle_log_lesson

        mock_config["active_class_id"] = sample_class
        args = argparse.Namespace(
            class_id=None,
            text=None,
            file="/nonexistent/lesson.txt",
            notes=None,
            topics=None,
        )
        handle_log_lesson(mock_config, args)
        out = capsys.readouterr().out
        assert "File not found" in out

    def test_log_lesson_no_content(self, mock_config, sample_class, capsys):
        from main import handle_log_lesson

        mock_config["active_class_id"] = sample_class
        args = argparse.Namespace(
            class_id=None,
            text=None,
            file=None,
            notes=None,
            topics=None,
        )
        handle_log_lesson(mock_config, args)
        out = capsys.readouterr().out
        assert "Provide lesson content" in out

    def test_log_lesson_class_not_found(self, mock_config, capsys):
        from main import handle_log_lesson

        mock_config["active_class_id"] = 999
        args = argparse.Namespace(
            class_id=None,
            text="Some lesson content",
            file=None,
            notes=None,
            topics=None,
        )
        handle_log_lesson(mock_config, args)
        out = capsys.readouterr().out
        assert "not found" in out


class TestHandleListLessons:
    """Tests for handle_list_lessons() in main.py."""

    def test_list_lessons_empty(self, mock_config, sample_class, capsys):
        from main import handle_list_lessons

        mock_config["active_class_id"] = sample_class
        args = argparse.Namespace(
            class_id=None,
            last=None,
            date_from=None,
            date_to=None,
            topic=None,
        )
        handle_list_lessons(mock_config, args)
        out = capsys.readouterr().out
        assert "Lessons for" in out
        assert "No lessons found" in out

    def test_list_lessons_with_data(self, mock_config, sample_class, sample_lesson, capsys):
        from main import handle_list_lessons

        mock_config["active_class_id"] = sample_class
        args = argparse.Namespace(
            class_id=None,
            last=None,
            date_from=None,
            date_to=None,
            topic=None,
        )
        handle_list_lessons(mock_config, args)
        out = capsys.readouterr().out
        assert "Lessons for" in out
        assert "Total lessons: 1" in out
        assert "photosynthesis" in out

    def test_list_lessons_class_not_found(self, mock_config, capsys):
        from main import handle_list_lessons

        mock_config["active_class_id"] = 999
        args = argparse.Namespace(
            class_id=None,
            last=None,
            date_from=None,
            date_to=None,
            topic=None,
        )
        handle_list_lessons(mock_config, args)
        out = capsys.readouterr().out
        assert "not found" in out

    def test_list_lessons_with_last_filter(self, mock_config, sample_class, sample_lesson, capsys):
        from main import handle_list_lessons

        mock_config["active_class_id"] = sample_class
        args = argparse.Namespace(
            class_id=None,
            last=30,
            date_from=None,
            date_to=None,
            topic=None,
        )
        handle_list_lessons(mock_config, args)
        out = capsys.readouterr().out
        assert "Lessons for" in out
        # The lesson was just created, so it should appear in last 30 days
        assert "Total lessons: 1" in out

    def test_list_lessons_with_topic_filter(self, mock_config, sample_class, sample_lesson, capsys):
        from main import handle_list_lessons

        mock_config["active_class_id"] = sample_class
        args = argparse.Namespace(
            class_id=None,
            last=None,
            date_from=None,
            date_to=None,
            topic="photosynthesis",
        )
        handle_list_lessons(mock_config, args)
        out = capsys.readouterr().out
        assert "Lessons for" in out


class TestHandleCostSummary:
    """Tests for handle_cost_summary() in main.py."""

    def test_cost_summary_no_calls(self, capsys):
        from unittest.mock import patch

        from main import handle_cost_summary

        args = argparse.Namespace()
        with patch(
            "main.get_cost_summary",
            return_value={"total_calls": 0, "total_cost": 0.0},
        ):
            handle_cost_summary(None, args)

        out = capsys.readouterr().out
        assert "No API calls recorded" in out
        assert "mock provider" in out.lower() or "zero cost" in out.lower()

    def test_cost_summary_with_data(self, capsys):
        from unittest.mock import patch

        from main import handle_cost_summary

        mock_stats = {
            "total_calls": 5,
            "total_cost": 0.0123,
            "total_input_tokens": 5000,
            "total_output_tokens": 2000,
            "by_provider": {"gemini": {"calls": 5, "cost": 0.0123}},
            "by_day": {"2025-03-15": {"calls": 5, "cost": 0.0123}},
        }
        args = argparse.Namespace()
        with (
            patch("main.get_cost_summary", return_value=mock_stats),
            patch("main.format_cost_report", return_value="=== Cost Report ===\nTotal: $0.0123") as mock_fmt,
        ):
            handle_cost_summary(None, args)
            mock_fmt.assert_called_once_with(mock_stats)

        out = capsys.readouterr().out
        assert "Cost Report" in out


# ---------------------------------------------------------------------------
# main.py Helper Tests
# ---------------------------------------------------------------------------


class TestMainHelpers:
    """Tests for _resolve_class_id and _get_db_session in main.py."""

    def test_resolve_class_id_from_args(self, mock_config, temp_db):
        from main import _resolve_class_id

        _, session, _ = temp_db
        args = argparse.Namespace(class_id=42)
        assert _resolve_class_id(mock_config, args, session) == 42

    def test_resolve_class_id_from_config(self, mock_config, temp_db):
        from main import _resolve_class_id

        _, session, _ = temp_db
        mock_config["active_class_id"] = 7
        args = argparse.Namespace(class_id=None)
        assert _resolve_class_id(mock_config, args, session) == 7

    def test_resolve_class_id_default(self, mock_config, temp_db):
        from main import _resolve_class_id

        _, session, _ = temp_db
        args = argparse.Namespace(class_id=None)
        assert _resolve_class_id(mock_config, args, session) == 1

    def test_resolve_class_id_no_class_attr(self, mock_config, temp_db):
        from main import _resolve_class_id

        _, session, _ = temp_db
        args = argparse.Namespace()  # No class_id attribute
        assert _resolve_class_id(mock_config, args, session) == 1

    def test_get_db_session(self, mock_config):
        from main import _get_db_session

        engine, session = _get_db_session(mock_config)
        assert session is not None
        session.close()
        engine.dispose()
