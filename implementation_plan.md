# Implementation Plan

[Overview]
Implement a robust "Generator-Critic" feedback loop to elevate the quiz generation process from a simple linear flow to a quality-assured agentic pipeline. This involves refactoring `src/agents.py` to support distinct `Generator` and `Critic` agents and creating an orchestration layer to manage their interaction.

The current system generates questions in a single pass, which often leads to quality issues or guideline violations. By introducing a Critic agent that reviews the output against strict `QA Guidelines`, and a feedback loop that allows the Generator to correct mistakes, we ensure high-quality, compliant output for the demo.

[Types]
No major type system changes (Python dynamic typing), but we will define clear dictionary structures for agent communication.

- `QuizDraft`: `List[Dict[str, Any]]` (The list of generated questions)
- `CriticFeedback`: `Dict[str, Any]`
    - `status`: "APPROVED" | "REJECTED"
    - `feedback`: `str` (Detailed list of violations if rejected)

[Files]
Single sentence describing file modifications.

- `src/agents.py`: Major refactor.
    - Create `GeneratorAgent` class.
    - Create `CriticAgent` class.
    - Create `Orchestrator` class/function.
    - Remove monolithic `generate_questions` function (replace with Orchestrator call).
- `main.py`: Update `handle_generate` to use the new Orchestrator.
- `prompts/generator_prompt.txt`: Verify and ensure it supports receiving feedback.
- `prompts/critic_prompt.txt`: Verify and ensure it aligns with the logic.

[Functions]
Single sentence describing function modifications.

- `src/agents.py`:
    - `load_prompt(filepath: str) -> str`: Helper to read prompt files.
    - `GeneratorAgent.generate(context: Dict, feedback: Optional[str]) -> List[Dict]`: Generates questions, optionally taking critique feedback to refine the next draft.
    - `CriticAgent.critique(questions: List[Dict], guidelines: str) -> Dict`: Reviews the draft and returns status and feedback.
    - `run_agentic_pipeline(config: Dict, ...) -> List[Dict]`: The new entry point replacing `generate_questions`.
- `main.py`:
    - `handle_generate`: Update to call `run_agentic_pipeline`.

[Classes]
Single sentence describing class modifications.

- `GeneratorAgent` (src/agents.py): Encapsulates generation logic, prompt construction, and interaction with LLMProvider.
- `CriticAgent` (src/agents.py): Encapsulates critique logic, prompt construction (validating against guidelines), and parsing LLM response.
- `Orchestrator` (src/agents.py): Manages the retry loop (max_retries), passing data between Generator and Critic.

[Dependencies]
Single sentence describing dependency modifications.

No new external dependencies. Relies on existing `src/llm_provider.py` and `src/database.py`.

[Testing]
Single sentence describing testing approach.

- `tests/test_agents.py`: Create new tests for the agentic loop.
    - Test Generator produces valid JSON.
    - Test Critic correctly identifies violations (mocked).
    - Test Orchestrator respects max_retries.
    - Test successful "APPROVED" flow.

[Implementation Order]
Single sentence describing the implementation sequence.

1.  Refactor `src/agents.py` to create `GeneratorAgent` and `CriticAgent` classes with prompt loading.
2.  Implement the `Orchestrator` logic with the feedback loop.
3.  Update `main.py` to use the new pipeline.
4.  Add unit tests in `tests/test_agents.py`.
5.  Verify the flow with a live run using `main.py generate`.
