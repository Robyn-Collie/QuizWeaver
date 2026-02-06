"""
Mock LLM response templates for cost-free development.

This module provides fabricated but realistic responses that simulate
real LLM API behavior without making external calls or incurring costs.
"""

import json
import random
from typing import Dict, List, Any


# Sample topics for generating realistic content
SCIENCE_TOPICS = [
    "photosynthesis", "cell division", "mitosis", "meiosis",
    "respiration", "genetics", "evolution", "ecosystems",
    "atomic structure", "chemical reactions", "forces", "energy"
]


def fill_template_context(template: str, context_keywords: List[str] = None) -> str:
    """
    Fill template with context-aware keywords.

    Args:
        template: Template string with {keyword} placeholders
        context_keywords: List of keywords from the prompt context

    Returns:
        Filled template string
    """
    if not context_keywords:
        context_keywords = random.sample(SCIENCE_TOPICS, k=min(3, len(SCIENCE_TOPICS)))

    replacements = {
        "topic1": context_keywords[0] if len(context_keywords) > 0 else "science",
        "topic2": context_keywords[1] if len(context_keywords) > 1 else "biology",
        "topic3": context_keywords[2] if len(context_keywords) > 2 else "chemistry",
    }

    result = template
    for key, value in replacements.items():
        result = result.replace(f"{{{key}}}", value)

    return result


def get_analyst_response(prompt_parts: List[Any]) -> str:
    """
    Generate mock analyst response (style profile JSON).

    The analyst agent examines content and determines quiz characteristics.

    Returns:
        JSON string with style profile
    """
    # Add some randomization to simulate real LLM variety
    image_ratio = random.choice([0.2, 0.25, 0.3, 0.35])
    question_count = random.choice([15, 20, 25, 30])

    response = {
        "estimated_question_count": question_count,
        "image_ratio": image_ratio,
        "difficulty_distribution": {
            "easy": 0.3,
            "medium": 0.5,
            "hard": 0.2
        },
        "question_types": {
            "multiple_choice": 0.7,
            "true_false": 0.2,
            "short_answer": 0.1
        },
        "topics_identified": random.sample(SCIENCE_TOPICS, k=random.randint(3, 6)),
        "recommended_points_per_question": 5,
        "notes": "Content appears to be grade 7-8 science level."
    }

    return json.dumps(response, indent=2)


def get_generator_response(prompt_parts: List[Any], context_keywords: List[str] = None) -> str:
    """
    Generate mock generator response (quiz questions JSON array).

    The generator agent creates quiz questions based on context.

    Returns:
        JSON string with array of questions
    """
    if not context_keywords:
        context_keywords = random.sample(SCIENCE_TOPICS, k=3)

    # Generate 3-5 mock questions
    num_questions = random.randint(3, 5)
    questions = []

    for i in range(num_questions):
        topic = context_keywords[i % len(context_keywords)]

        # Randomly choose question type
        q_type = random.choice(["multiple_choice", "true_false"])

        if q_type == "multiple_choice":
            question = {
                "type": "multiple_choice",
                "title": f"Question {i+1}",
                "text": f"Which of the following best describes {topic}?",
                "points": 5,
                "options": [
                    f"Option A about {topic}",
                    f"Option B about {topic}",
                    f"Option C about {topic}",
                    f"Option D about {topic}"
                ],
                "correct_index": random.randint(0, 3),
                "image_ref": None if random.random() > 0.3 else f"image_{i+1}.png"
            }
        else:  # true_false
            question = {
                "type": "true_false",
                "title": f"Question {i+1}",
                "text": f"{topic.capitalize()} is a fundamental concept in science.",
                "points": 5,
                "options": ["True", "False"],
                "correct_index": random.randint(0, 1),
                "image_ref": None
            }

        questions.append(question)

    return json.dumps(questions, indent=2)


def get_critic_response(prompt_parts: List[Any], iteration: int = 1) -> str:
    """
    Generate mock critic response (approval/feedback JSON).

    The critic agent reviews questions and provides feedback.
    Alternates between approval and revision to test both paths.

    Args:
        prompt_parts: The prompt context
        iteration: Which iteration (used to alternate responses)

    Returns:
        JSON string with approval status and feedback
    """
    # Alternate between approved and needs_revision for testing
    if iteration % 2 == 0:
        response = {
            "status": "approved",
            "feedback": "Questions are well-structured and align with the lesson content. Grade level is appropriate.",
            "suggested_changes": []
        }
    else:
        response = {
            "status": "needs_revision",
            "feedback": "Some questions need clearer wording.",
            "suggested_changes": [
                {
                    "question_index": 0,
                    "issue": "Question is too ambiguous",
                    "suggestion": "Add more specific details about the concept"
                },
                {
                    "question_index": 2,
                    "issue": "Difficulty mismatch",
                    "suggestion": "This question seems too advanced for the grade level"
                }
            ]
        }

    return json.dumps(response, indent=2)


def get_mock_response(prompt_parts: List[Any], json_mode: bool = False,
                      agent_type: str = "generator") -> str:
    """
    Main entry point for getting mock responses.

    Determines which agent template to use based on context clues.

    Args:
        prompt_parts: List of prompt parts (text and images)
        json_mode: Whether response should be JSON
        agent_type: Type of agent (analyst, generator, critic)

    Returns:
        Fabricated response string
    """
    # Extract text from prompt_parts for context
    text_parts = [p for p in prompt_parts if isinstance(p, str)]
    combined_text = " ".join(text_parts).lower()

    # Extract keywords for context-aware responses
    context_keywords = [topic for topic in SCIENCE_TOPICS if topic in combined_text]
    if not context_keywords:
        context_keywords = random.sample(SCIENCE_TOPICS, k=3)

    # Detect agent type from prompt if not explicitly provided
    if "style" in combined_text or "analyze" in combined_text:
        agent_type = "analyst"
    elif "review" in combined_text or "critic" in combined_text or "feedback" in combined_text:
        agent_type = "critic"
    else:
        agent_type = "generator"

    # Return appropriate response
    if agent_type == "analyst":
        return get_analyst_response(prompt_parts)
    elif agent_type == "critic":
        # Use hash of prompt to determine iteration (for determinism within a session)
        iteration = hash(str(prompt_parts)) % 10
        return get_critic_response(prompt_parts, iteration)
    else:  # generator
        return get_generator_response(prompt_parts, context_keywords)
