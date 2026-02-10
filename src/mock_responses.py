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

        # Add cognitive tags if framework detected
        if cognitive_framework and cognitive_levels:
            level_idx = i % len(cognitive_levels)
            question["cognitive_level"] = cognitive_levels[level_idx]
            question["cognitive_framework"] = cognitive_framework
            question["cognitive_level_number"] = level_idx + 1

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


def get_study_material_response(prompt_parts: List[Any], material_type: str,
                                context_keywords: List[str] = None) -> str:
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
            {"front": f"What is {topic1}?", "back": f"The process of {topic1} in living organisms.", "tags": [topic1, "definition"]},
            {"front": f"Define {topic2}", "back": f"{topic2.capitalize()} is a fundamental concept in science that involves cellular processes.", "tags": [topic2]},
            {"front": f"Key function of {topic3}", "back": f"{topic3.capitalize()} plays an essential role in maintaining biological systems.", "tags": [topic3]},
            {"front": f"Stages of {topic1}", "back": f"Stage 1: Initiation, Stage 2: Progression, Stage 3: Completion of {topic1}.", "tags": [topic1, "stages"]},
            {"front": f"Compare {topic1} and {topic2}", "back": f"{topic1.capitalize()} involves energy conversion while {topic2} involves structural changes.", "tags": [topic1, topic2, "comparison"]},
            {"front": f"Where does {topic1} occur?", "back": f"{topic1.capitalize()} primarily occurs in specialized cellular structures.", "tags": [topic1, "location"]},
            {"front": f"Why is {topic2} important?", "back": f"{topic2.capitalize()} is essential for growth, repair, and reproduction.", "tags": [topic2, "importance"]},
            {"front": f"Products of {topic3}", "back": f"The main products of {topic3} include energy and waste byproducts.", "tags": [topic3, "products"]},
            {"front": f"Factors affecting {topic1}", "back": f"Temperature, light, and availability of resources affect the rate of {topic1}.", "tags": [topic1, "factors"]},
            {"front": f"Real-world application of {topic2}", "back": f"{topic2.capitalize()} has applications in medicine, agriculture, and biotechnology.", "tags": [topic2, "application"]},
        ]
    elif material_type == "study_guide":
        items = [
            {"heading": f"Introduction to {topic1.capitalize()}", "content": f"{topic1.capitalize()} is a fundamental process in biology. It involves the conversion of energy and materials within living systems. Understanding {topic1} is essential for grasping how organisms function.", "key_points": [f"{topic1.capitalize()} is a core biological process", "It involves energy transformation", "All living organisms depend on it"]},
            {"heading": f"{topic2.capitalize()}: Key Concepts", "content": f"{topic2.capitalize()} encompasses several important mechanisms. These mechanisms work together to maintain the structure and function of living organisms. Students should focus on the relationship between {topic2} and overall organism health.", "key_points": [f"{topic2.capitalize()} has multiple components", "It is critical for organism survival", f"Related to {topic1}"]},
            {"heading": f"The Role of {topic3.capitalize()}", "content": f"{topic3.capitalize()} is closely related to both {topic1} and {topic2}. It provides the chemical basis for many biological reactions. Understanding {topic3} helps explain why organisms need specific nutrients.", "key_points": [f"{topic3.capitalize()} supports biological reactions", f"Connected to {topic1} and {topic2}", "Explains nutrient requirements"]},
            {"heading": "Review and Connections", "content": f"All three topics -- {topic1}, {topic2}, and {topic3} -- are interconnected. Changes in one process can affect the others. For the assessment, focus on how these processes work together in living systems.", "key_points": ["Topics are interconnected", "Changes propagate between systems", "Focus on integration for assessment"]},
        ]
    elif material_type == "vocabulary":
        items = [
            {"term": topic1.capitalize(), "definition": f"The biological process of {topic1} in living organisms.", "example": f"Plants use {topic1} to convert sunlight into energy.", "part_of_speech": "noun"},
            {"term": topic2.capitalize(), "definition": f"A fundamental concept involving {topic2} in cellular biology.", "example": f"{topic2.capitalize()} occurs during cell growth.", "part_of_speech": "noun"},
            {"term": topic3.capitalize(), "definition": f"The study and process of {topic3} in biological systems.", "example": f"{topic3.capitalize()} reactions occur in the mitochondria.", "part_of_speech": "noun"},
            {"term": "Organism", "definition": "An individual living thing that can function independently.", "example": "A tree is a complex organism.", "part_of_speech": "noun"},
            {"term": "Cellular", "definition": "Relating to or consisting of living cells.", "example": "Cellular processes keep organisms alive.", "part_of_speech": "adjective"},
            {"term": "Metabolism", "definition": "The chemical processes that occur within a living organism to maintain life.", "example": f"Metabolism includes both {topic1} and {topic3}.", "part_of_speech": "noun"},
            {"term": "Enzyme", "definition": "A substance produced by a living organism that acts as a catalyst.", "example": f"Enzymes speed up {topic3} reactions.", "part_of_speech": "noun"},
            {"term": "Substrate", "definition": "The substance on which an enzyme acts.", "example": "The substrate binds to the enzyme's active site.", "part_of_speech": "noun"},
        ]
    elif material_type == "review_sheet":
        items = [
            {"heading": f"Key Formula: {topic1.capitalize()}", "content": f"6CO2 + 6H2O -> C6H12O6 + 6O2 (simplified equation for {topic1})", "type": "formula"},
            {"heading": f"Important Fact: {topic2.capitalize()}", "content": f"{topic2.capitalize()} is divided into distinct phases, each with specific characteristics and outcomes.", "type": "fact"},
            {"heading": f"Core Concept: {topic3.capitalize()}", "content": f"{topic3.capitalize()} involves breaking down complex molecules into simpler ones, releasing energy in the process. This energy is stored as ATP.", "type": "concept"},
            {"heading": "Key Dates and Discoveries", "content": f"The process of {topic1} was first described in detail in the early 1800s. Modern understanding has expanded significantly.", "type": "fact"},
            {"heading": f"Comparison: {topic1.capitalize()} vs {topic3.capitalize()}", "content": f"{topic1.capitalize()} builds complex molecules (anabolic) while {topic3} breaks them down (catabolic). Both are essential for life.", "type": "concept"},
            {"heading": "Quick Reference: Cell Structures", "content": f"Chloroplast: site of {topic1}. Mitochondria: site of {topic3}. Nucleus: controls {topic2}.", "type": "fact"},
        ]
    else:
        items = [
            {"front": f"What is {topic1}?", "back": f"A key concept in science.", "tags": [topic1]},
        ]

    return json.dumps(items, indent=2)


def get_variant_response(questions_data: List[Dict], reading_level: str,
                         context_keywords: List[str] = None) -> str:
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


def get_rubric_response(questions_data: List[Dict], style_profile: Dict = None,
                        context_keywords: List[str] = None) -> str:
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
                {"level": 1, "label": "Beginning", "description": f"Shows minimal understanding of {topic} concepts. Unable to identify basic facts."},
                {"level": 2, "label": "Developing", "description": f"Shows partial understanding of {topic} concepts. Can identify some basic facts."},
                {"level": 3, "label": "Proficient", "description": f"Demonstrates solid understanding of {topic} concepts. Correctly applies knowledge."},
                {"level": 4, "label": "Advanced", "description": f"Shows deep understanding of {topic} concepts. Makes connections across topics."},
            ],
        },
        {
            "criterion": "Scientific Vocabulary",
            "description": f"Uses appropriate scientific terminology related to {topic}",
            "max_points": 5,
            "levels": [
                {"level": 1, "label": "Beginning", "description": "Rarely uses scientific terms or uses them incorrectly."},
                {"level": 2, "label": "Developing", "description": "Sometimes uses scientific terms but with limited accuracy."},
                {"level": 3, "label": "Proficient", "description": "Consistently uses scientific terms accurately."},
                {"level": 4, "label": "Advanced", "description": "Uses precise scientific vocabulary and explains terms in context."},
            ],
        },
        {
            "criterion": "Critical Thinking",
            "description": "Applies analysis and reasoning to answer questions",
            "max_points": 10,
            "levels": [
                {"level": 1, "label": "Beginning", "description": "Provides answers without reasoning or evidence."},
                {"level": 2, "label": "Developing", "description": "Shows some reasoning but conclusions may be unsupported."},
                {"level": 3, "label": "Proficient", "description": "Applies logical reasoning with supporting evidence."},
                {"level": 4, "label": "Advanced", "description": "Demonstrates sophisticated analysis with multiple perspectives."},
            ],
        },
        {
            "criterion": "Application of Concepts",
            "description": f"Applies {topic} concepts to new scenarios",
            "max_points": 10,
            "levels": [
                {"level": 1, "label": "Beginning", "description": "Cannot apply concepts beyond memorized examples."},
                {"level": 2, "label": "Developing", "description": "Can apply concepts in familiar contexts only."},
                {"level": 3, "label": "Proficient", "description": "Successfully applies concepts to new but similar scenarios."},
                {"level": 4, "label": "Advanced", "description": "Creatively applies concepts to novel and complex scenarios."},
            ],
        },
    ]

    # Add a multiple-choice-specific criterion if MC questions exist
    if "multiple_choice" in q_types or "mc" in q_types:
        criteria.append({
            "criterion": "Multiple Choice Analysis",
            "description": "Ability to evaluate options and eliminate distractors",
            "max_points": 5,
            "levels": [
                {"level": 1, "label": "Beginning", "description": "Selects answers randomly without analysis."},
                {"level": 2, "label": "Developing", "description": "Can eliminate one distractor but struggles with similar options."},
                {"level": 3, "label": "Proficient", "description": "Correctly identifies the best answer by eliminating distractors."},
                {"level": 4, "label": "Advanced", "description": "Explains why each distractor is incorrect and defends the correct choice."},
            ],
        })

    return json.dumps(criteria, indent=2)


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
        # Use hash of prompt to determine iteration (for determinism within a session)
        iteration = hash(str(prompt_parts)) % 10
        return get_critic_response(prompt_parts, iteration)
    else:  # generator
        return get_generator_response(prompt_parts, context_keywords)
