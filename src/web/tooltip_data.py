"""
Centralized AI literacy tooltip text for QuizWeaver.

All tooltip strings are stored here for easy updates and consistency.
Tooltips explain AI concepts in plain, empowering language.
"""

# AI Literacy tooltips keyed by location identifier.
# These complement existing field-level help-tips with educational context
# about how AI works, what it can/cannot do, and responsible use.

AI_TOOLTIPS = {
    # Quiz generation form
    "cognitive_framework": (
        "Cognitive levels (Bloom's, DOK) are set by rules, not by AI. "
        "The AI generates content within these fixed educational constraints."
    ),
    "provider_selection": (
        "Real AI providers (Gemini, OpenAI) charge per request based on text length. "
        "Mock mode is free but returns placeholder content, not lesson-aligned questions."
    ),
    "generation_data": (
        "The AI receives your lesson summaries, topics, and standards to generate questions. "
        "No student names or personal data is sent."
    ),

    # Quiz detail / review page
    "review_reminder": (
        "AI-generated questions are drafts. Review each question for accuracy, "
        "bias, and grade-level appropriateness before sharing with students."
    ),

    # Study material pages
    "study_review": (
        "Always verify AI-generated study content against your lesson materials. "
        "AI can produce plausible-sounding but inaccurate information."
    ),

    # Settings page
    "api_key_privacy": (
        "Your API key is stored locally on this computer only. "
        "It is never shared with QuizWeaver or any third party."
    ),
    "mock_provider": (
        "Mock mode generates placeholder content at zero cost. "
        "Use it to explore QuizWeaver before connecting a real AI provider."
    ),

    # Lesson logging
    "lesson_privacy": (
        "Lesson content you enter here may be sent to your AI provider during quiz generation. "
        "Never include student names or personally identifiable information."
    ),

    # Rubric detail
    "rubric_review": (
        "Rubric criteria are structured by fixed proficiency levels, but descriptions "
        "are AI-generated drafts. Verify they match your assessment expectations."
    ),
}
