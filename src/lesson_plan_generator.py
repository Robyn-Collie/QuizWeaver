"""
Lesson plan generator for QuizWeaver.

Generates standards-aligned lesson plans with all required sections
using the LLM pipeline. Uses MockLLMProvider by default for zero-cost development.
"""

import copy
import json
import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from src.classroom import get_class
from src.database import LessonPlan

logger = logging.getLogger(__name__)

LESSON_PLAN_SECTIONS = [
    "learning_objectives",
    "materials_needed",
    "warm_up",
    "direct_instruction",
    "guided_practice",
    "independent_practice",
    "assessment",
    "closure",
    "differentiation",
    "standards_alignment",
]

SECTION_LABELS = {
    "learning_objectives": "Learning Objectives",
    "materials_needed": "Materials Needed",
    "warm_up": "Warm-Up (5-10 min)",
    "direct_instruction": "Direct Instruction (10-15 min)",
    "guided_practice": "Guided Practice (10-15 min)",
    "independent_practice": "Independent Practice (10-15 min)",
    "assessment": "Assessment / Check for Understanding (5 min)",
    "closure": "Closure (3-5 min)",
    "differentiation": "Differentiation",
    "standards_alignment": "Standards Alignment",
}


def _build_prompt(class_obj, topics, standards, duration_minutes, grade_level):
    """Build the LLM prompt for lesson plan generation."""
    parts = [
        "Generate a detailed lesson plan for a classroom lesson.",
        "",
        f"Class: {class_obj.name}",
    ]
    if grade_level:
        parts.append(f"Grade Level: {grade_level}")
    elif class_obj.grade_level:
        parts.append(f"Grade Level: {class_obj.grade_level}")

    if class_obj.subject:
        parts.append(f"Subject: {class_obj.subject}")

    if topics:
        parts.append(f"Topics: {', '.join(topics)}")

    if standards:
        parts.append(f"Standards: {', '.join(standards)}")

    parts.append(f"Duration: {duration_minutes} minutes")

    parts.append("")
    parts.append("Return a JSON object with these keys, each containing a string value:")
    parts.append("- title: A descriptive lesson title")
    parts.append("- learning_objectives: 2-4 objectives (what students will know/be able to do)")
    parts.append("- materials_needed: List of required materials")
    parts.append("- warm_up: Warm-up activity (5-10 min) to activate prior knowledge")
    parts.append("- direct_instruction: Teacher-led content delivery (10-15 min)")
    parts.append("- guided_practice: Teacher-supported practice activities (10-15 min)")
    parts.append("- independent_practice: Student independent work (10-15 min)")
    parts.append("- assessment: How to verify learning / check for understanding (5 min)")
    parts.append("- closure: Summarize and preview next lesson (3-5 min)")
    parts.append("- differentiation: Modifications for below grade, on grade, and advanced learners")
    parts.append("- standards_alignment: Which standards are addressed and how")

    return "\n".join(parts)


def _parse_plan(response_text):
    """Parse JSON response into a plan data dict."""
    try:
        data = json.loads(response_text)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    # Try to extract JSON object from response
    import re

    match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass

    logger.warning("Failed to parse lesson plan response")
    return None


def generate_lesson_plan(
    session: Session,
    class_id: int,
    config: dict,
    topics: Optional[List[str]] = None,
    standards: Optional[List[str]] = None,
    duration_minutes: int = 50,
    grade_level: Optional[str] = None,
    provider_name: Optional[str] = None,
) -> Optional[LessonPlan]:
    """Generate a standards-aligned lesson plan.

    Args:
        session: SQLAlchemy session.
        class_id: ID of the class to generate for.
        config: Application config dict (must include llm.provider).
        topics: Optional list of topics to cover.
        standards: Optional list of standards to align to.
        duration_minutes: Lesson duration in minutes (default 50).
        grade_level: Optional grade level override.
        provider_name: Optional provider override.

    Returns:
        LessonPlan ORM object, or None on failure.
    """
    if provider_name:
        config = copy.deepcopy(config)
        config.setdefault("llm", {})["provider"] = provider_name

    class_obj = get_class(session, class_id)
    if class_obj is None:
        logger.warning("generate_lesson_plan: class_id=%s not found", class_id)
        return None

    # Create lesson plan record with generating status
    plan = LessonPlan(
        class_id=class_id,
        title="Generating...",
        topics=json.dumps(topics or []),
        standards=json.dumps(standards or []),
        grade_level=grade_level or (class_obj.grade_level if hasattr(class_obj, "grade_level") else None),
        duration_minutes=duration_minutes,
        plan_data=json.dumps({}),
        status="generating",
    )
    session.add(plan)
    session.commit()

    # Build prompt
    prompt = _build_prompt(class_obj, topics, standards, duration_minutes, grade_level)

    # Get LLM response
    try:
        current_provider = config.get("llm", {}).get("provider", "mock")
        if current_provider == "mock":
            from src.mock_responses import SCIENCE_TOPICS, get_lesson_plan_response

            context_lower = prompt.lower()
            keywords = [t for t in SCIENCE_TOPICS if t in context_lower]
            response_text = get_lesson_plan_response(topics or [], standards or [], duration_minutes, keywords or None)
        else:
            from src.llm_provider import get_provider

            provider = get_provider(config, web_mode=True)
            response_text = provider.generate([prompt], json_mode=True)

    except Exception as e:
        logger.error("generate_lesson_plan: LLM call failed: %s", e)
        plan.status = "failed"
        session.commit()
        return None

    # Parse response
    plan_data = _parse_plan(response_text)
    if not plan_data:
        plan.status = "failed"
        session.commit()
        return None

    # Update plan with parsed data
    title = plan_data.pop("title", None)
    if title:
        plan.title = title
    else:
        topic_label = ", ".join(topics) if topics else (class_obj.subject or "Lesson")
        plan.title = f"Lesson Plan: {topic_label}"

    plan.plan_data = json.dumps(plan_data)
    plan.status = "draft"
    session.commit()
    session.refresh(plan)

    return plan
