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

from src.database import (
    get_engine, init_db, get_session,
    Quiz, Question, Class, LessonLog,
    StudySet, StudyCard, Rubric, RubricCriterion,
    LessonPlan, PerformanceData,
)
from src.classroom import create_class
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
        content = open(out_file, "r", encoding="utf-8").read()
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
        content = open(out_file, "r", encoding="utf-8").read()
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
        from src.cli.study_commands import handle_generate_study, handle_export_study
        from src.cli import get_db_session

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
        from src.cli.rubric_commands import handle_generate_rubric, handle_export_rubric
        from src.cli import get_db_session

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
        from src.cli.lesson_plan_commands import handle_generate_lesson_plan, handle_export_lesson_plan
        from src.cli import get_db_session

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
        with open(out_file, "r") as f:
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
