"""
Reusable quiz generation function for QuizWeaver.

Extracts the core quiz generation logic from main.py:handle_generate()
into a function that can be called by both the CLI and the web frontend.
Uses MockLLMProvider by default for zero-cost development.

Run tests with: python -m pytest tests/test_quiz_generator.py -v
"""

import copy
import json
import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from src.agents import run_agentic_pipeline
from src.classroom import get_class
from src.cognitive_frameworks import validate_distribution
from src.database import Question, Quiz

logger = logging.getLogger(__name__)


def generate_quiz(
    session: Session,
    class_id: int,
    config: dict,
    num_questions: int = 20,
    grade_level: Optional[str] = None,
    sol_standards: Optional[List[str]] = None,
    cognitive_framework: Optional[str] = None,
    cognitive_distribution: Optional[dict] = None,
    difficulty: int = 3,
    provider_name: Optional[str] = None,
) -> Optional[Quiz]:
    """
    Generate a quiz for a given class using the agentic pipeline.

    Args:
        session: SQLAlchemy session (caller is responsible for lifecycle)
        class_id: ID of the Class to generate for
        config: Application config dict (must include llm.provider)
        num_questions: Number of questions to request (default 20)
        grade_level: Override grade level; falls back to class grade_level,
                     then config default
        sol_standards: List of SOL standards to target; falls back to config
        cognitive_framework: "blooms" or "dok" or None
        cognitive_distribution: dict mapping level number to question count
        difficulty: Difficulty level 1-5 (default 3)
        provider_name: Override provider (e.g., "openai", "mock"). If None,
                       uses config default.

    Returns:
        A Quiz ORM object with questions attached, or None on failure
    """
    # Apply provider override if specified
    run_config = config
    if provider_name:
        run_config = copy.deepcopy(config)
        run_config["llm"]["provider"] = provider_name

    # Validate class exists
    class_obj = get_class(session, class_id)
    if class_obj is None:
        logger.warning("generate_quiz: class_id=%s not found", class_id)
        return None

    # Resolve grade level: explicit arg > class > config default
    resolved_grade = grade_level
    if resolved_grade is None:
        resolved_grade = class_obj.grade_level
    if resolved_grade is None:
        resolved_grade = config.get("generation", {}).get("default_grade_level", "7th Grade Science")

    # Resolve SOL standards: explicit arg > config default
    resolved_sol = sol_standards
    if resolved_sol is None:
        resolved_sol = config.get("generation", {}).get("sol_standards", [])

    # Validate cognitive distribution if provided
    validated_framework = cognitive_framework
    validated_distribution = cognitive_distribution
    if cognitive_framework and cognitive_distribution:
        is_valid, error_msg = validate_distribution(cognitive_framework, cognitive_distribution, num_questions)
        if not is_valid:
            logger.warning("generate_quiz: invalid cognitive distribution: %s", error_msg)
            validated_framework = None
            validated_distribution = None

    # Build style profile
    style_profile = {
        "grade_level": resolved_grade,
        "sol_standards": resolved_sol,
        "num_questions": num_questions,
        "cognitive_framework": validated_framework,
        "cognitive_distribution": validated_distribution,
        "difficulty": difficulty,
        "provider": run_config.get("llm", {}).get("provider", "mock"),
    }

    # Create quiz record with status "generating"
    quiz_title = config.get("generation", {}).get("quiz_title", "Generated Quiz")
    new_quiz = Quiz(
        title=quiz_title,
        class_id=class_id,
        status="generating",
        style_profile=json.dumps(style_profile),
    )
    session.add(new_quiz)
    session.commit()

    # Build generation context
    context = {
        "content_summary": "",
        "structured_data": [],
        "retake_text": "",
        "num_questions": num_questions,
        "images": [],
        "image_ratio": run_config.get("generation", {}).get("target_image_ratio", 0.0),
        "grade_level": resolved_grade,
        "sol_standards": resolved_sol,
        "cognitive_framework": validated_framework,
        "cognitive_distribution": validated_distribution,
        "difficulty": difficulty,
    }

    # Run the agentic pipeline (enriches context with class lessons/knowledge)
    try:
        questions_data = run_agentic_pipeline(run_config, context, class_id=class_id, web_mode=True)
    except Exception as e:
        logger.error("generate_quiz: pipeline crashed: %s", e)
        new_quiz.status = "failed"
        session.commit()
        return None

    if not questions_data:
        logger.warning("generate_quiz: pipeline returned no questions")
        new_quiz.status = "failed"
        session.commit()
        return None

    # Store questions
    for idx, q_data in enumerate(questions_data):
        question_record = Question(
            quiz_id=new_quiz.id,
            question_type=q_data.get("type"),
            title=q_data.get("title"),
            text=q_data.get("text"),
            points=q_data.get("points"),
            sort_order=idx,
            data=q_data,
        )
        session.add(question_record)

    new_quiz.status = "generated"
    session.commit()

    # Refresh to populate the questions relationship
    session.refresh(new_quiz)

    return new_quiz
