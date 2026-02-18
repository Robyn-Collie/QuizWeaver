"""
Mock LLM response templates for cost-free development.

This module provides fabricated but realistic responses that simulate
real LLM API behavior without making external calls or incurring costs.
"""

import json
import random
from typing import Any, Dict, List

# Sample topics for generating realistic content
SCIENCE_TOPICS = [
    "photosynthesis",
    "cell division",
    "mitosis",
    "meiosis",
    "respiration",
    "genetics",
    "evolution",
    "ecosystems",
    "atomic structure",
    "chemical reactions",
    "forces",
    "energy",
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

    Args:
        prompt_parts: List of prompt parts (text strings and image contexts).

    Returns:
        JSON string with style profile including question count, image ratio,
        difficulty distribution, and identified topics.
    """
    # Add some randomization to simulate real LLM variety
    image_ratio = random.choice([0.2, 0.25, 0.3, 0.35])
    question_count = random.choice([15, 20, 25, 30])

    response = {
        "estimated_question_count": question_count,
        "image_ratio": image_ratio,
        "difficulty_distribution": {"easy": 0.3, "medium": 0.5, "hard": 0.2},
        "question_types": {"multiple_choice": 0.7, "true_false": 0.2, "short_answer": 0.1},
        "topics_identified": random.sample(SCIENCE_TOPICS, k=random.randint(3, 6)),
        "recommended_points_per_question": 5,
        "notes": "Content appears to be grade 7-8 science level.",
    }

    return json.dumps(response, indent=2)


BLOOMS_LEVEL_NAMES = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]
DOK_LEVEL_NAMES = ["Recall", "Skill/Concept", "Strategic Thinking", "Extended Thinking"]


def get_generator_response(prompt_parts: List[Any], context_keywords: List[str] = None) -> str:
    """
    Generate mock generator response (quiz questions JSON array).

    The generator agent creates quiz questions based on context.

    Args:
        prompt_parts: List of prompt parts (text strings and image contexts).
        context_keywords: Optional list of topic keywords extracted from the prompt.
            If None, random science topics are selected.

    Returns:
        JSON string with array of 3-5 question objects, each containing
        type, title, text, points, options, correct_index, and image_ref.
    """
    if not context_keywords:
        context_keywords = random.sample(SCIENCE_TOPICS, k=3)

    # Detect cognitive framework from prompt
    combined_text = " ".join(str(p) for p in prompt_parts).lower()
    cognitive_framework = None
    cognitive_levels = None
    if "bloom" in combined_text:
        cognitive_framework = "blooms"
        cognitive_levels = BLOOMS_LEVEL_NAMES
    elif "dok" in combined_text or "webb" in combined_text:
        cognitive_framework = "dok"
        cognitive_levels = DOK_LEVEL_NAMES

    # Generate 5-7 mock questions (mix of types)
    num_questions = random.randint(5, 7)
    questions = []
    has_image = False

    for i in range(num_questions):
        topic = context_keywords[i % len(context_keywords)]

        # Randomly choose question type including new types
        q_type = random.choice(
            [
                "multiple_choice",
                "multiple_choice",
                "true_false",
                "ordering",
                "short_answer",
                "fill_in",
                "multiple_answer",
                "stimulus",
                "cloze",
            ]
        )

        if q_type == "cloze":
            topic2 = context_keywords[(i + 1) % len(context_keywords)]
            topic3 = context_keywords[(i + 2) % len(context_keywords)]
            question = {
                "type": "cloze",
                "title": f"Question {i + 1}",
                "text": (
                    "The {{1}} is a fundamental process in biology. "
                    "During {{2}}, organisms convert {{3}} into usable energy."
                ),
                "blanks": [
                    {"id": 1, "answer": topic, "alternatives": [f"{topic} process"]},
                    {"id": 2, "answer": topic2, "alternatives": []},
                    {"id": 3, "answer": topic3, "alternatives": [f"raw {topic3}"]},
                ],
                "points": 3,
                "image_ref": None,
            }
        elif q_type == "stimulus":
            # Stimulus: shared passage with 2-3 sub-questions
            topic2 = context_keywords[(i + 1) % len(context_keywords)]
            question = {
                "type": "stimulus",
                "title": f"Question {i + 1}",
                "text": f"Read the following passage about {topic} and answer the questions below.",
                "stimulus_text": (
                    f"{topic.capitalize()} is a fundamental biological process that occurs in living organisms. "
                    f"Scientists have studied {topic} extensively and discovered that it involves multiple stages. "
                    f"The first stage begins with the absorption of {topic2}, followed by a series of chemical "
                    f"reactions that produce energy. This energy is then used by the organism for growth, "
                    f"repair, and reproduction. Without {topic}, life as we know it would not be possible."
                ),
                "image_url": None,
                "sub_questions": [
                    {
                        "type": "mc",
                        "text": f"Based on the passage, what is the primary role of {topic}?",
                        "options": [
                            "To produce energy for the organism",
                            f"To eliminate {topic2} from the body",
                            "To slow down chemical reactions",
                            "To reduce the need for reproduction",
                        ],
                        "correct_index": 0,
                        "points": 1,
                    },
                    {
                        "type": "tf",
                        "text": f"According to the passage, {topic} involves multiple stages.",
                        "correct_answer": "True",
                        "points": 1,
                    },
                    {
                        "type": "short_answer",
                        "text": f"Name one purpose that organisms use the energy from {topic} for, according to the passage.",
                        "expected_answer": "growth",
                        "acceptable_answers": ["growth", "repair", "reproduction"],
                        "points": 1,
                    },
                ],
                "points": 3,
                "image_ref": None,
            }
        elif q_type == "multiple_choice":
            question = {
                "type": "multiple_choice",
                "title": f"Question {i + 1}",
                "text": f"Which of the following best describes {topic}?",
                "points": 5,
                "options": [
                    f"Option A about {topic}",
                    f"Option B about {topic}",
                    f"Option C about {topic}",
                    f"Option D about {topic}",
                ],
                "correct_index": random.randint(0, 3),
                "image_ref": None if random.random() > 0.3 else f"image_{i + 1}.png",
            }
        elif q_type == "true_false":
            question = {
                "type": "true_false",
                "title": f"Question {i + 1}",
                "text": f"{topic.capitalize()} is a fundamental concept in science.",
                "points": 5,
                "options": ["True", "False"],
                "correct_index": random.randint(0, 1),
                "image_ref": None,
            }
        elif q_type == "ordering":
            steps = [
                f"First, identify the {topic} components",
                f"Next, observe the {topic} process beginning",
                f"Then, measure the {topic} output",
                f"Finally, record the {topic} results",
            ]
            question = {
                "type": "ordering",
                "question_type": "ordering",
                "title": f"Question {i + 1}",
                "text": f"Arrange the steps of the {topic} experiment in the correct order.",
                "points": 5,
                "items": steps,
                "correct_order": [0, 1, 2, 3],
                "instructions": "Arrange the following steps in the correct order.",
                "image_ref": None,
            }
        elif q_type == "fill_in":
            distractors = ["osmosis", "diffusion", "fermentation"]
            word_bank = [topic] + distractors[:3]
            random.shuffle(word_bank)
            question = {
                "type": "fill_in",
                "question_type": "fill_in",
                "title": f"Question {i + 1}",
                "text": "The process of ___ converts light energy into chemical energy in plants.",
                "points": 5,
                "correct_answer": topic,
                "word_bank": word_bank,
                "image_ref": None,
            }
        elif q_type == "multiple_answer":
            # Select 2 correct indices from 4 options
            correct_indices = sorted(random.sample(range(4), 2))
            question = {
                "type": "multiple_answer",
                "question_type": "multiple_answer",
                "title": f"Question {i + 1}",
                "text": f"Select ALL that apply. Which of the following are true about {topic}?",
                "points": 5,
                "options": [
                    f"{topic.capitalize()} involves energy conversion",
                    f"{topic.capitalize()} occurs only in animals",
                    f"{topic.capitalize()} is a biological process",
                    f"{topic.capitalize()} requires no enzymes",
                ],
                "correct_indices": correct_indices,
                "image_ref": None,
            }
        else:  # short_answer
            question = {
                "type": "short_answer",
                "question_type": "short_answer",
                "title": f"Question {i + 1}",
                "text": f"What is the primary function of {topic} in living organisms?",
                "points": 5,
                "expected_answer": f"{topic}",
                "acceptable_answers": [
                    topic,
                    f"the process of {topic}",
                    f"{topic} in cells",
                ],
                "rubric_hint": f"Student should mention the role of {topic} in biological systems.",
                "image_ref": None,
            }

        # Add cognitive tags if framework detected
        if cognitive_framework and cognitive_levels:
            level_idx = i % len(cognitive_levels)
            question["cognitive_level"] = cognitive_levels[level_idx]
            question["cognitive_framework"] = cognitive_framework
            question["cognitive_level_number"] = level_idx + 1

        # Add smart image fields when a question has an image_ref
        if question.get("image_ref"):
            has_image = True
            question["image_description"] = f"Diagram illustrating {topic} in a biological context"
            question["image_search_terms"] = [topic, "diagram", "biology"]
            # First image question reveals the answer, others don't
            question["image_reveals_answer"] = i == 0

        questions.append(question)

    # Ensure at least one question has smart image fields for realistic mocking
    if not has_image and questions:
        first_topic = context_keywords[0] if context_keywords else "science"
        questions[0]["image_description"] = f"Diagram illustrating {first_topic} in a biological context"
        questions[0]["image_search_terms"] = [first_topic, "diagram", "biology"]
        questions[0]["image_reveals_answer"] = False

    return json.dumps(questions, indent=2)


def get_critic_response(prompt_parts: List[Any], iteration: int = 1) -> str:
    """Generate mock critic response (approval/feedback JSON).

    .. deprecated::
        Use the structured JSON format returned by ``get_mock_response()``
        with ``agent_type="critic"`` instead.  This legacy function returns
        lowercase status values that don't match the new ``"PASS"/"FAIL"``
        per-question verdict format.

    Args:
        prompt_parts: The prompt context
        iteration: Which iteration (used to alternate responses)

    Returns:
        JSON string with approval status and feedback (legacy format).
    """
    import warnings

    warnings.warn(
        "get_critic_response() is deprecated; use get_mock_response(agent_type='critic') "
        "for the structured per-question verdict format.",
        DeprecationWarning,
        stacklevel=2,
    )
    # Alternate between approved and needs_revision for testing
    if iteration % 2 == 0:
        response = {
            "status": "approved",
            "feedback": "Questions are well-structured and align with the lesson content. Grade level is appropriate.",
            "suggested_changes": [],
        }
    else:
        response = {
            "status": "needs_revision",
            "feedback": "Some questions need clearer wording.",
            "suggested_changes": [
                {
                    "question_index": 0,
                    "issue": "Question is too ambiguous",
                    "suggestion": "Add more specific details about the concept",
                },
                {
                    "question_index": 2,
                    "issue": "Difficulty mismatch",
                    "suggestion": "This question seems too advanced for the grade level",
                },
            ],
        }

    return json.dumps(response, indent=2)


def get_study_material_response(prompt_parts: List[Any], material_type: str, context_keywords: List[str] = None) -> str:
    """
    Generate mock study material response based on material type.

    Args:
        prompt_parts: List of prompt parts (text and images).
        material_type: One of flashcard, study_guide, vocabulary, review_sheet.
        context_keywords: Optional topic keywords from the prompt.

    Returns:
        JSON string with study material items.
    """
    if not context_keywords:
        context_keywords = random.sample(SCIENCE_TOPICS, k=3)

    topic1 = context_keywords[0] if len(context_keywords) > 0 else "science"
    topic2 = context_keywords[1] if len(context_keywords) > 1 else "biology"
    topic3 = context_keywords[2] if len(context_keywords) > 2 else "chemistry"

    if material_type == "flashcard":
        items = [
            {
                "front": f"What is {topic1}?",
                "back": f"The process of {topic1} in living organisms.",
                "tags": [topic1, "definition"],
            },
            {
                "front": f"Define {topic2}",
                "back": f"{topic2.capitalize()} is a fundamental concept in science that involves cellular processes.",
                "tags": [topic2],
            },
            {
                "front": f"Key function of {topic3}",
                "back": f"{topic3.capitalize()} plays an essential role in maintaining biological systems.",
                "tags": [topic3],
            },
            {
                "front": f"Stages of {topic1}",
                "back": f"Stage 1: Initiation, Stage 2: Progression, Stage 3: Completion of {topic1}.",
                "tags": [topic1, "stages"],
            },
            {
                "front": f"Compare {topic1} and {topic2}",
                "back": f"{topic1.capitalize()} involves energy conversion while {topic2} involves structural changes.",
                "tags": [topic1, topic2, "comparison"],
            },
            {
                "front": f"Where does {topic1} occur?",
                "back": f"{topic1.capitalize()} primarily occurs in specialized cellular structures.",
                "tags": [topic1, "location"],
            },
            {
                "front": f"Why is {topic2} important?",
                "back": f"{topic2.capitalize()} is essential for growth, repair, and reproduction.",
                "tags": [topic2, "importance"],
            },
            {
                "front": f"Products of {topic3}",
                "back": f"The main products of {topic3} include energy and waste byproducts.",
                "tags": [topic3, "products"],
            },
            {
                "front": f"Factors affecting {topic1}",
                "back": f"Temperature, light, and availability of resources affect the rate of {topic1}.",
                "tags": [topic1, "factors"],
            },
            {
                "front": f"Real-world application of {topic2}",
                "back": f"{topic2.capitalize()} has applications in medicine, agriculture, and biotechnology.",
                "tags": [topic2, "application"],
            },
        ]
    elif material_type == "study_guide":
        items = [
            {
                "heading": f"Introduction to {topic1.capitalize()}",
                "content": f"{topic1.capitalize()} is a fundamental process in biology. It involves the conversion of energy and materials within living systems. Understanding {topic1} is essential for grasping how organisms function.",
                "key_points": [
                    f"{topic1.capitalize()} is a core biological process",
                    "It involves energy transformation",
                    "All living organisms depend on it",
                ],
            },
            {
                "heading": f"{topic2.capitalize()}: Key Concepts",
                "content": f"{topic2.capitalize()} encompasses several important mechanisms. These mechanisms work together to maintain the structure and function of living organisms. Students should focus on the relationship between {topic2} and overall organism health.",
                "key_points": [
                    f"{topic2.capitalize()} has multiple components",
                    "It is critical for organism survival",
                    f"Related to {topic1}",
                ],
            },
            {
                "heading": f"The Role of {topic3.capitalize()}",
                "content": f"{topic3.capitalize()} is closely related to both {topic1} and {topic2}. It provides the chemical basis for many biological reactions. Understanding {topic3} helps explain why organisms need specific nutrients.",
                "key_points": [
                    f"{topic3.capitalize()} supports biological reactions",
                    f"Connected to {topic1} and {topic2}",
                    "Explains nutrient requirements",
                ],
            },
            {
                "heading": "Review and Connections",
                "content": f"All three topics -- {topic1}, {topic2}, and {topic3} -- are interconnected. Changes in one process can affect the others. For the assessment, focus on how these processes work together in living systems.",
                "key_points": [
                    "Topics are interconnected",
                    "Changes propagate between systems",
                    "Focus on integration for assessment",
                ],
            },
        ]
    elif material_type == "vocabulary":
        items = [
            {
                "term": topic1.capitalize(),
                "definition": f"The biological process of {topic1} in living organisms.",
                "example": f"Plants use {topic1} to convert sunlight into energy.",
                "part_of_speech": "noun",
            },
            {
                "term": topic2.capitalize(),
                "definition": f"A fundamental concept involving {topic2} in cellular biology.",
                "example": f"{topic2.capitalize()} occurs during cell growth.",
                "part_of_speech": "noun",
            },
            {
                "term": topic3.capitalize(),
                "definition": f"The study and process of {topic3} in biological systems.",
                "example": f"{topic3.capitalize()} reactions occur in the mitochondria.",
                "part_of_speech": "noun",
            },
            {
                "term": "Organism",
                "definition": "An individual living thing that can function independently.",
                "example": "A tree is a complex organism.",
                "part_of_speech": "noun",
            },
            {
                "term": "Cellular",
                "definition": "Relating to or consisting of living cells.",
                "example": "Cellular processes keep organisms alive.",
                "part_of_speech": "adjective",
            },
            {
                "term": "Metabolism",
                "definition": "The chemical processes that occur within a living organism to maintain life.",
                "example": f"Metabolism includes both {topic1} and {topic3}.",
                "part_of_speech": "noun",
            },
            {
                "term": "Enzyme",
                "definition": "A substance produced by a living organism that acts as a catalyst.",
                "example": f"Enzymes speed up {topic3} reactions.",
                "part_of_speech": "noun",
            },
            {
                "term": "Substrate",
                "definition": "The substance on which an enzyme acts.",
                "example": "The substrate binds to the enzyme's active site.",
                "part_of_speech": "noun",
            },
        ]
    elif material_type == "review_sheet":
        items = [
            {
                "heading": f"Key Formula: {topic1.capitalize()}",
                "content": f"6CO2 + 6H2O -> C6H12O6 + 6O2 (simplified equation for {topic1})",
                "type": "formula",
            },
            {
                "heading": f"Important Fact: {topic2.capitalize()}",
                "content": f"{topic2.capitalize()} is divided into distinct phases, each with specific characteristics and outcomes.",
                "type": "fact",
            },
            {
                "heading": f"Core Concept: {topic3.capitalize()}",
                "content": f"{topic3.capitalize()} involves breaking down complex molecules into simpler ones, releasing energy in the process. This energy is stored as ATP.",
                "type": "concept",
            },
            {
                "heading": "Key Dates and Discoveries",
                "content": f"The process of {topic1} was first described in detail in the early 1800s. Modern understanding has expanded significantly.",
                "type": "fact",
            },
            {
                "heading": f"Comparison: {topic1.capitalize()} vs {topic3.capitalize()}",
                "content": f"{topic1.capitalize()} builds complex molecules (anabolic) while {topic3} breaks them down (catabolic). Both are essential for life.",
                "type": "concept",
            },
            {
                "heading": "Quick Reference: Cell Structures",
                "content": f"Chloroplast: site of {topic1}. Mitochondria: site of {topic3}. Nucleus: controls {topic2}.",
                "type": "fact",
            },
        ]
    else:
        items = [
            {"front": f"What is {topic1}?", "back": "A key concept in science.", "tags": [topic1]},
        ]

    return json.dumps(items, indent=2)


def get_variant_response(questions_data: List[Dict], reading_level: str, context_keywords: List[str] = None) -> str:
    """Generate mock variant response by modifying question text for reading level.

    Args:
        questions_data: List of question dicts from the source quiz.
        reading_level: Target reading level (ell, below_grade, on_grade, advanced).
        context_keywords: Optional topic keywords.

    Returns:
        JSON string with array of rewritten question objects.
    """
    level_adjustments = {
        "ell": {
            "prefix": "What is",
            "suffix": "(Choose the best answer.)",
            "simplify": True,
        },
        "below_grade": {
            "prefix": "Look at the choices below.",
            "suffix": "(Hint: Think about what you learned in class.)",
            "simplify": True,
        },
        "on_grade": {
            "prefix": "",
            "suffix": "",
            "simplify": False,
        },
        "advanced": {
            "prefix": "Analyze and evaluate",
            "suffix": "Support your reasoning.",
            "simplify": False,
        },
    }
    adj = level_adjustments.get(reading_level, level_adjustments["on_grade"])

    result = []
    for i, q in enumerate(questions_data):
        new_q = dict(q)
        original_text = q.get("text", "")

        if adj["simplify"]:
            # Simplify: shorten text, use simpler language
            if adj["prefix"]:
                new_q["text"] = f"{adj['prefix']} {original_text.lower().rstrip('?.')}? {adj['suffix']}".strip()
            else:
                new_q["text"] = original_text
        else:
            if adj["prefix"]:
                new_q["text"] = f"{adj['prefix']} the following: {original_text} {adj['suffix']}".strip()
            else:
                new_q["text"] = original_text

        new_q["title"] = f"Question {i + 1}"
        result.append(new_q)

    return json.dumps(result, indent=2)


def get_rubric_response(
    questions_data: List[Dict], style_profile: Dict = None, context_keywords: List[str] = None
) -> str:
    """Generate mock rubric response with criteria and proficiency levels.

    Args:
        questions_data: List of question dicts from the quiz.
        style_profile: Optional style profile dict with framework/standards info.
        context_keywords: Optional topic keywords.

    Returns:
        JSON string with array of criterion objects.
    """
    if not context_keywords:
        context_keywords = random.sample(SCIENCE_TOPICS, k=3)

    topic = context_keywords[0] if context_keywords else "science"

    # Detect question types present
    q_types = set()
    for q in questions_data:
        q_types.add(q.get("type", q.get("question_type", "multiple_choice")))

    criteria = [
        {
            "criterion": "Content Knowledge",
            "description": f"Demonstrates understanding of key {topic} concepts",
            "max_points": 10,
            "levels": [
                {
                    "level": 1,
                    "label": "Beginning",
                    "description": f"Shows minimal understanding of {topic} concepts. Unable to identify basic facts.",
                },
                {
                    "level": 2,
                    "label": "Developing",
                    "description": f"Shows partial understanding of {topic} concepts. Can identify some basic facts.",
                },
                {
                    "level": 3,
                    "label": "Proficient",
                    "description": f"Demonstrates solid understanding of {topic} concepts. Correctly applies knowledge.",
                },
                {
                    "level": 4,
                    "label": "Advanced",
                    "description": f"Shows deep understanding of {topic} concepts. Makes connections across topics.",
                },
            ],
        },
        {
            "criterion": "Scientific Vocabulary",
            "description": f"Uses appropriate scientific terminology related to {topic}",
            "max_points": 5,
            "levels": [
                {
                    "level": 1,
                    "label": "Beginning",
                    "description": "Rarely uses scientific terms or uses them incorrectly.",
                },
                {
                    "level": 2,
                    "label": "Developing",
                    "description": "Sometimes uses scientific terms but with limited accuracy.",
                },
                {"level": 3, "label": "Proficient", "description": "Consistently uses scientific terms accurately."},
                {
                    "level": 4,
                    "label": "Advanced",
                    "description": "Uses precise scientific vocabulary and explains terms in context.",
                },
            ],
        },
        {
            "criterion": "Critical Thinking",
            "description": "Applies analysis and reasoning to answer questions",
            "max_points": 10,
            "levels": [
                {"level": 1, "label": "Beginning", "description": "Provides answers without reasoning or evidence."},
                {
                    "level": 2,
                    "label": "Developing",
                    "description": "Shows some reasoning but conclusions may be unsupported.",
                },
                {
                    "level": 3,
                    "label": "Proficient",
                    "description": "Applies logical reasoning with supporting evidence.",
                },
                {
                    "level": 4,
                    "label": "Advanced",
                    "description": "Demonstrates sophisticated analysis with multiple perspectives.",
                },
            ],
        },
        {
            "criterion": "Application of Concepts",
            "description": f"Applies {topic} concepts to new scenarios",
            "max_points": 10,
            "levels": [
                {"level": 1, "label": "Beginning", "description": "Cannot apply concepts beyond memorized examples."},
                {"level": 2, "label": "Developing", "description": "Can apply concepts in familiar contexts only."},
                {
                    "level": 3,
                    "label": "Proficient",
                    "description": "Successfully applies concepts to new but similar scenarios.",
                },
                {
                    "level": 4,
                    "label": "Advanced",
                    "description": "Creatively applies concepts to novel and complex scenarios.",
                },
            ],
        },
    ]

    # Add a multiple-choice-specific criterion if MC questions exist
    if "multiple_choice" in q_types or "mc" in q_types:
        criteria.append(
            {
                "criterion": "Multiple Choice Analysis",
                "description": "Ability to evaluate options and eliminate distractors",
                "max_points": 5,
                "levels": [
                    {"level": 1, "label": "Beginning", "description": "Selects answers randomly without analysis."},
                    {
                        "level": 2,
                        "label": "Developing",
                        "description": "Can eliminate one distractor but struggles with similar options.",
                    },
                    {
                        "level": 3,
                        "label": "Proficient",
                        "description": "Correctly identifies the best answer by eliminating distractors.",
                    },
                    {
                        "level": 4,
                        "label": "Advanced",
                        "description": "Explains why each distractor is incorrect and defends the correct choice.",
                    },
                ],
            }
        )

    return json.dumps(criteria, indent=2)


def get_reteach_response(gap_data: List[Dict], focus_topics: List[str] = None, max_suggestions: int = 5) -> str:
    """Generate mock re-teach suggestion response.

    Args:
        gap_data: List of gap analysis dicts from compute_gap_analysis.
        focus_topics: Optional list of topics to focus on.
        max_suggestions: Maximum number of suggestions.

    Returns:
        JSON string with array of suggestion objects.
    """
    # Filter to focus topics if provided
    items = gap_data or []
    if focus_topics:
        items = [g for g in items if g.get("topic") in focus_topics]
    if not items:
        items = gap_data[:max_suggestions] if gap_data else []

    suggestions = []
    activities_pool = [
        ["Guided notes with visual organizers", "Think-pair-share discussion", "Exit ticket quiz (3 questions)"],
        ["Hands-on lab activity", "Jigsaw reading groups", "Concept mapping exercise"],
        ["Interactive simulation", "Gallery walk with peer feedback", "Quick-write reflection"],
        ["Station rotation with practice problems", "Vocabulary card sort", "Diagram labeling activity"],
        ["Video analysis with guided questions", "Role-play scenario", "Graphic organizer completion"],
    ]

    resources_pool = [
        ["Textbook Ch. 4, pp. 87-92", "Khan Academy video series", "Teacher-created study guide"],
        ["Interactive website simulation", "Printed graphic organizer template", "Vocabulary flashcard set"],
        ["Lab materials kit", "Supplemental reading passage", "Practice worksheet (differentiated)"],
    ]

    for i, item in enumerate(items[:max_suggestions]):
        topic = item.get("topic", "Unknown topic")
        actual = item.get("actual_score", 0.5)
        severity = item.get("gap_severity", "concerning")

        target = min(actual + 0.20, 1.0)

        priority_map = {"critical": "high", "concerning": "medium", "on_track": "low", "exceeding": "low"}

        suggestion = {
            "topic": topic,
            "gap_severity": severity,
            "current_score": round(actual, 2),
            "target_score": round(target, 2),
            "lesson_plan": (
                f"Re-teach {topic} using a multi-modal approach. Begin with a brief "
                f"diagnostic assessment to identify specific misconceptions. Follow with "
                f"direct instruction using visual aids and real-world examples. "
                f"Include guided practice with immediate feedback and close with an "
                f"independent practice opportunity."
            ),
            "activities": activities_pool[i % len(activities_pool)],
            "estimated_duration": f"{30 + (i % 3) * 15} minutes",
            "resources": resources_pool[i % len(resources_pool)],
            "assessment_suggestion": (
                f"Administer a 5-question formative assessment on {topic} "
                f"one week after re-teaching to measure improvement."
            ),
            "priority": priority_map.get(severity, "medium"),
        }
        suggestions.append(suggestion)

    return json.dumps(suggestions, indent=2)


def get_lesson_plan_response(
    topics: List[str] = None,
    standards: List[str] = None,
    duration_minutes: int = 50,
    context_keywords: List[str] = None,
) -> str:
    """Generate mock lesson plan response with all required sections.

    Args:
        topics: List of topics to cover.
        standards: List of standards to align to.
        duration_minutes: Lesson duration in minutes.
        context_keywords: Optional topic keywords from prompt context.

    Returns:
        JSON string with a lesson plan object containing all sections.
    """
    if not context_keywords:
        context_keywords = random.sample(SCIENCE_TOPICS, k=3)

    topic1 = context_keywords[0] if len(context_keywords) > 0 else "science"
    topic2 = context_keywords[1] if len(context_keywords) > 1 else "biology"
    topic3 = context_keywords[2] if len(context_keywords) > 2 else "chemistry"

    topic_label = ", ".join(topics) if topics else topic1.capitalize()
    standards_label = ", ".join(standards) if standards else "SOL 7.1, SOL 7.2"

    plan = {
        "title": f"Exploring {topic_label}",
        "learning_objectives": (
            f"Students will be able to: (1) Define {topic1} and explain its role in living organisms. "
            f"(2) Identify the key stages of {topic1}. "
            f"(3) Compare and contrast {topic1} with {topic2}. "
            f"(4) Apply knowledge of {topic1} to real-world scenarios."
        ),
        "materials_needed": (
            f"Textbook (Chapter 5), whiteboard and markers, {topic1} diagram handout, "
            f"colored pencils, exit ticket slips, laptop/projector for presentation, "
            f"lab materials for {topic1} demonstration (if available)."
        ),
        "warm_up": (
            f"Display a photograph related to {topic1} on the projector. "
            f"Ask students to write 3 observations and 1 question about what they see. "
            f"After 3 minutes, have 2-3 students share their observations with the class. "
            f"Use student responses to bridge into the day's topic."
        ),
        "direct_instruction": (
            f"Present a mini-lecture on {topic1} using slides. Cover the definition, "
            f"the key stages, and how it connects to {topic2}. Use the diagram handout "
            f"to illustrate the process step by step. Pause after each stage to check "
            f"understanding with quick thumbs-up/thumbs-down. Emphasize vocabulary terms: "
            f"{topic1}, {topic2}, {topic3}."
        ),
        "guided_practice": (
            f"Students work in pairs to complete the {topic1} diagram labeling activity. "
            f"Teacher circulates the room to provide support and answer questions. "
            f"After 10 minutes, review the diagram as a class. Students correct their "
            f"work using a different colored pencil. Discuss common misconceptions."
        ),
        "independent_practice": (
            f"Students independently answer 5 short-response questions about {topic1} "
            f"in their notebooks. Questions progress from recall to application. "
            f"Early finishers may begin the extension activity: writing a paragraph "
            f"explaining how {topic1} connects to {topic3} in everyday life."
        ),
        "assessment": (
            f"Exit ticket: Students answer 2 questions on a slip of paper. "
            f"(1) Explain the main purpose of {topic1} in one sentence. "
            f"(2) Name two factors that affect the rate of {topic1}. "
            f"Collect exit tickets as formative assessment data."
        ),
        "closure": (
            f"Review the learning objectives. Ask students to rate their confidence "
            f"on a scale of 1-5 with a hand signal. Preview tomorrow's lesson: "
            f"we will explore {topic2} in more depth and conduct a hands-on lab. "
            f"Remind students to review their notes for homework."
        ),
        "differentiation": (
            f"Below Grade Level: Provide a pre-filled diagram with word bank for the "
            f"labeling activity. Pair with a stronger partner. Simplify exit ticket to "
            f"multiple choice. "
            f"On Grade Level: Complete standard activities as described. "
            f"Advanced: Add a critical thinking question to the exit ticket asking "
            f"students to predict what would happen if {topic1} were disrupted. "
            f"Encourage independent research on {topic3} applications."
        ),
        "standards_alignment": (
            f"This lesson addresses {standards_label}. "
            f"The warm-up activates prior knowledge ({standards_label.split(',')[0].strip()}). "
            f"Direct instruction and guided practice build conceptual understanding. "
            f"Independent practice and assessment check for mastery of key objectives."
        ),
    }

    return json.dumps(plan, indent=2)


def get_exit_ticket_response(num_questions: int = 3, context_keywords: List[str] = None) -> str:
    """Generate mock exit ticket response (1-5 simple questions).

    Args:
        num_questions: Number of questions to generate (1-5).
        context_keywords: Optional topic keywords.

    Returns:
        JSON string with array of exit ticket question objects.
    """
    if not context_keywords:
        context_keywords = random.sample(SCIENCE_TOPICS, k=3)

    num_questions = max(1, min(5, num_questions))
    questions = []
    types_cycle = ["multiple_choice", "true_false", "short_answer"]

    for i in range(num_questions):
        topic = context_keywords[i % len(context_keywords)]
        q_type = types_cycle[i % len(types_cycle)]

        if q_type == "multiple_choice":
            question = {
                "type": "multiple_choice",
                "title": f"Question {i + 1}",
                "text": f"What is the main purpose of {topic}?",
                "points": 1,
                "options": [
                    f"To support {topic} processes",
                    f"To inhibit {topic} reactions",
                    f"To measure {topic} output",
                    f"To prevent {topic} changes",
                ],
                "correct_index": 0,
            }
        elif q_type == "true_false":
            question = {
                "type": "true_false",
                "title": f"Question {i + 1}",
                "text": f"{topic.capitalize()} is essential for living organisms.",
                "points": 1,
                "options": ["True", "False"],
                "correct_index": 0,
            }
        else:  # short_answer
            question = {
                "type": "short_answer",
                "title": f"Question {i + 1}",
                "text": f"Name one key component of {topic}.",
                "points": 1,
                "expected_answer": f"A component of {topic}",
                "acceptable_answers": [topic, f"{topic} component"],
            }

        questions.append(question)

    return json.dumps(questions, indent=2)


def _get_structured_critic_response(prompt_parts: List[Any]) -> str:
    """Return a structured per-question critic response in the new JSON format.

    Uses a deterministic hash of the prompt to decide per-question verdicts,
    giving roughly a 2/3 approval rate.  This lets tests exercise both the
    approved and rejected paths without randomness.
    """
    # Try to figure out how many questions are in the draft
    combined = " ".join(str(p) for p in prompt_parts)
    num_questions = 5  # default
    try:
        # The quiz draft is embedded as JSON in the prompt
        bracket_start = combined.rfind("[")
        bracket_end = combined.rfind("]")
        if bracket_start != -1 and bracket_end != -1:
            snippet = combined[bracket_start : bracket_end + 1]
            parsed = json.loads(snippet)
            if isinstance(parsed, list):
                num_questions = len(parsed)
    except (json.JSONDecodeError, ValueError):
        pass

    verdicts = []
    for i in range(num_questions):
        # Deterministic: use hash of prompt + index to decide pass/fail
        h = hash((str(prompt_parts)[:200], i)) % 3
        if h == 0:
            # ~1/3 fail
            verdicts.append(
                {
                    "index": i,
                    "verdict": "FAIL",
                    "issues": ["Mock critic: question wording could be clearer"],
                    "fact_check": "WARN",
                    "fact_check_notes": "Mock critic: unable to verify factual accuracy",
                    "suggestions": "Consider rephrasing for clarity",
                }
            )
        else:
            verdicts.append(
                {
                    "index": i,
                    "verdict": "PASS",
                    "issues": [],
                    "fact_check": "PASS",
                    "fact_check_notes": "",
                    "suggestions": "",
                }
            )

    response = {
        "questions": verdicts,
        "overall_notes": "Mock critic review complete.",
    }
    return json.dumps(response, indent=2)


def get_mock_response(prompt_parts: List[Any], json_mode: bool = False, agent_type: str = "generator") -> str:
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

    # Check for exit ticket regardless of json_mode
    if "exit ticket" in combined_text or "exit_ticket" in combined_text:
        import re

        num_match = re.search(r"(\d+)\s+exit ticket", combined_text)
        num_q = int(num_match.group(1)) if num_match else 3
        return get_exit_ticket_response(num_q, context_keywords)

    # When json_mode is True the caller is the GeneratorAgent; honour
    # the default agent_type ("generator") instead of auto-detecting,
    # because generator prompts contain words like "style" that would
    # incorrectly trigger the analyst path.
    if not json_mode:
        # Auto-detect agent type from prompt text
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
        return _get_structured_critic_response(prompt_parts)
    else:  # generator
        return get_generator_response(prompt_parts, context_keywords)
