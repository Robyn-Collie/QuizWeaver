"""
Exit ticket generator for QuizWeaver.

Generates short formative assessments (1-5 questions) for end-of-class
check-for-understanding. Uses the LLM provider but skips the critic agent
since exit tickets are informal formative assessments.
"""

import copy
import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.classroom import get_class
from src.database import Question, Quiz
from src.lesson_tracker import get_recent_lessons
from src.llm_provider import get_provider

logger = logging.getLogger(__name__)

# Exit tickets are capped at 5 questions max
MAX_EXIT_TICKET_QUESTIONS = 5
MIN_EXIT_TICKET_QUESTIONS = 1


def generate_exit_ticket(
    session: Session,
    class_id: int,
    config: dict,
    lesson_log_id: Optional[int] = None,
    topic: Optional[str] = None,
    num_questions: int = 3,
    title: Optional[str] = None,
    provider_name: Optional[str] = None,
) -> Optional[Quiz]:
    """Generate a short exit ticket quiz for formative assessment.

    Args:
        session: SQLAlchemy session
        class_id: ID of the Class
        config: Application config dict
        lesson_log_id: Optional specific lesson log to base questions on
        topic: Optional free-text topic (used when no lesson_log_id)
        num_questions: Number of questions (1-5, default 3)
        title: Optional title override
        provider_name: Optional provider override

    Returns:
        A Quiz ORM object with questions, or None on failure
    """
    # Validate class
    class_obj = get_class(session, class_id)
    if class_obj is None:
        logger.warning("generate_exit_ticket: class_id=%s not found", class_id)
        return None

    # Clamp question count
    num_questions = max(MIN_EXIT_TICKET_QUESTIONS, min(MAX_EXIT_TICKET_QUESTIONS, num_questions))

    # Apply provider override
    run_config = config
    if provider_name:
        run_config = copy.deepcopy(config)
        run_config["llm"]["provider"] = provider_name

    # Resolve topic context
    topic_context = ""
    if lesson_log_id:
        from src.database import LessonLog

        lesson_log = session.query(LessonLog).filter_by(id=lesson_log_id).first()
        if lesson_log:
            topic_context = f"Lesson: {lesson_log.topics or ''}\nNotes: {lesson_log.notes or ''}"
            if not title:
                title = f"Exit Ticket - {lesson_log.topics or 'Lesson'}"

    if not topic_context and topic:
        topic_context = f"Topic: {topic}"

    if not topic_context:
        # Fall back to recent lessons
        recent = get_recent_lessons(session, class_id, days=7)
        if recent:
            topics = [lesson.topics for lesson in recent if lesson.topics]
            topic_context = f"Recent topics: {', '.join(str(t) for t in topics[:3])}"

    if not title:
        title = f"Exit Ticket - {topic or 'Check for Understanding'}"

    # Build style profile
    grade_level = class_obj.grade_level or config.get("generation", {}).get("default_grade_level", "7th Grade")
    provider = run_config.get("llm", {}).get("provider", "mock")
    model = run_config.get("llm", {}).get("model")

    style_profile = {
        "exit_ticket": True,
        "grade_level": grade_level,
        "num_questions": num_questions,
        "provider": provider,
        "model": model,
    }

    # Create quiz record
    new_quiz = Quiz(
        title=title,
        class_id=class_id,
        status="generating",
        style_profile=json.dumps(style_profile),
    )
    session.add(new_quiz)
    session.commit()

    # Build prompt for LLM
    prompt = _build_exit_ticket_prompt(topic_context, num_questions, grade_level)

    # Call LLM (no critic pass for exit tickets)
    try:
        llm = get_provider(run_config, web_mode=True)
        response = llm.generate([prompt], json_mode=True)
        questions_data = json.loads(response)
        if not isinstance(questions_data, list):
            questions_data = questions_data.get("questions", [])
    except Exception as e:
        logger.error("generate_exit_ticket: LLM call failed: %s", e)
        new_quiz.status = "failed"
        session.commit()
        return None

    if not questions_data:
        logger.warning("generate_exit_ticket: no questions generated")
        new_quiz.status = "failed"
        session.commit()
        return None

    # Limit to requested count
    questions_data = questions_data[:num_questions]

    # Store questions
    for idx, q_data in enumerate(questions_data):
        # Ensure points default
        if not q_data.get("points"):
            q_data["points"] = 1

        question_record = Question(
            quiz_id=new_quiz.id,
            question_type=q_data.get("type", "mc"),
            title=q_data.get("title", f"Question {idx + 1}"),
            text=q_data.get("text", ""),
            points=q_data.get("points", 1),
            sort_order=idx,
            data=q_data,
        )
        session.add(question_record)

    new_quiz.status = "generated"
    session.commit()
    session.refresh(new_quiz)
    return new_quiz


def _build_exit_ticket_prompt(topic_context: str, num_questions: int, grade_level: str) -> str:
    """Build the LLM prompt for exit ticket generation."""
    return f"""Generate {num_questions} exit ticket questions for a {grade_level} class.

Exit tickets are short formative assessments to check for understanding at the end of class.
Questions should target Bloom's Remember and Understand levels.

Context:
{topic_context}

Requirements:
- Generate exactly {num_questions} questions
- Mix of question types: multiple choice, true/false, and short answer
- Each question worth 1 point
- Keep questions concise and focused
- Questions should be answerable in 1-2 minutes each

Return a JSON array of question objects. Each object must have:
- "type": "multiple_choice", "true_false", or "short_answer"
- "title": question title
- "text": the question text
- "points": 1
- For MC: "options" (array of 4 strings), "correct_index" (0-based int)
- For TF: "options" ["True", "False"], "correct_index" (0 or 1)
- For short_answer: "expected_answer" (string), "acceptable_answers" (array of strings)
"""
