"""
Re-teach suggestion generator for QuizWeaver.

Generates AI-powered re-teaching suggestions based on gap analysis data.
Uses MockLLMProvider by default for zero-cost development.
"""

import copy
import json
import logging
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from src.database import Class
from src.performance_analytics import compute_gap_analysis

logger = logging.getLogger(__name__)


def _parse_suggestions(response_text: str) -> Optional[List[Dict]]:
    """Parse JSON response into list of suggestion dicts."""
    try:
        items = json.loads(response_text)
        if isinstance(items, list):
            return items
    except (json.JSONDecodeError, ValueError):
        pass

    import re

    match = re.search(r"\[.*\]", response_text, re.DOTALL)
    if match:
        try:
            items = json.loads(match.group())
            if isinstance(items, list):
                return items
        except (json.JSONDecodeError, ValueError):
            pass

    logger.warning("Failed to parse re-teach response")
    return None


def generate_reteach_suggestions(
    session: Session,
    class_id: int,
    config: dict,
    focus_topics: Optional[List[str]] = None,
    max_suggestions: int = 5,
    provider_name: Optional[str] = None,
) -> Optional[List[Dict]]:
    """Generate re-teach suggestions based on gap analysis.

    Args:
        session: SQLAlchemy session.
        class_id: Class to generate suggestions for.
        config: Application config dict.
        focus_topics: Optional list of topic names to focus on.
        max_suggestions: Maximum number of suggestions to generate.

    Returns:
        List of suggestion dicts, or None on failure.
    """
    # Apply provider override if specified
    if provider_name:
        config = copy.deepcopy(config)
        config.setdefault("llm", {})["provider"] = provider_name

    # Verify class exists
    class_obj = session.query(Class).filter_by(id=class_id).first()
    if not class_obj:
        logger.warning("generate_reteach_suggestions: class_id=%s not found", class_id)
        return None

    # Get gap analysis data
    gap_data = compute_gap_analysis(session, class_id)
    if not gap_data:
        logger.info("generate_reteach_suggestions: no gap data for class_id=%s", class_id)
        return []

    # Filter to weak areas (negative gap or concerning/critical)
    weak_gaps = [g for g in gap_data if g["gap_severity"] in ("critical", "concerning")]
    if not weak_gaps and not focus_topics:
        # Nothing concerning, return empty
        return []

    # Use all gap data if focus_topics specified (user knows what they want)
    relevant_gaps = gap_data if focus_topics else weak_gaps

    try:
        provider_name = config.get("llm", {}).get("provider", "mock")

        if provider_name == "mock":
            from src.mock_responses import get_reteach_response

            response_text = get_reteach_response(relevant_gaps, focus_topics, max_suggestions)
        else:
            # Build prompt for real LLM
            prompt = _build_prompt(class_obj, relevant_gaps, focus_topics, max_suggestions)
            from src.llm_provider import get_provider

            provider = get_provider(config, web_mode=True)
            response_text = provider.generate([prompt], json_mode=True)

    except Exception as e:
        logger.error("generate_reteach_suggestions: LLM call failed: %s", e)
        return None

    suggestions = _parse_suggestions(response_text)
    if suggestions is None:
        return None

    # Limit to max
    return suggestions[:max_suggestions]


def _build_prompt(class_obj, gap_data, focus_topics, max_suggestions):
    """Build LLM prompt for re-teach suggestions."""
    lines = [
        "Generate re-teaching suggestions for a class based on performance gaps.",
        f"\nClass: {class_obj.name}",
    ]
    if class_obj.grade_level:
        lines.append(f"Grade Level: {class_obj.grade_level}")
    if class_obj.subject:
        lines.append(f"Subject: {class_obj.subject}")

    lines.append(f"\nPerformance Gaps ({len(gap_data)} topics):")
    for g in gap_data[:10]:
        lines.append(
            f"  - {g['topic']}: actual={g['actual_score']:.0%}, "
            f"expected={g['expected_score']:.0%}, gap={g['gap']:+.0%}, "
            f"severity={g['gap_severity']}"
        )

    if focus_topics:
        lines.append(f"\nFocus on these topics: {', '.join(focus_topics)}")

    lines.append(
        f"\nGenerate up to {max_suggestions} re-teach suggestions as a JSON array. "
        f"Each suggestion should have: topic, gap_severity, current_score, "
        f"target_score, lesson_plan, activities (array), estimated_duration, "
        f"resources (array), assessment_suggestion, priority (high/medium/low)."
    )

    return "\n".join(lines)
