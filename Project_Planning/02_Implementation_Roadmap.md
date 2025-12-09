# Implementation Roadmap: Quiz Generation Platform

**Version:** 1.0
**Status:** Planning

---

## 1. Objective

This roadmap outlines the phased development plan to transition the Quiz Retake Generator from a single script proof-of-concept into a robust, agentic pipeline. Each phase is designed to deliver a discrete set of functionalities, culminating in a production-ready system that showcases advanced data engineering and Agentic AI principles.

---

## 2. Development Phases

### Phase 1: Foundational Refactoring & Modularization (Current Phase)
*   **Goal:** Deconstruct the monolithic `main.py` into a clean, modular architecture and introduce an LLM abstraction layer.
*   **Key Tasks:**
    1.  **Create Core Library:** Establish a `src` directory.
    2.  **Isolate Functionality:** Create distinct modules for `ingestion`, `database`, `agents`, and `output`.
    3.  **Implement LLM Provider Abstraction:**
        *   Create `src/llm_provider.py` with a base `LLMProvider` class.
        *   Implement a `GeminiProvider` as the first concrete implementation.
        *   Refactor the `agents.py` module to use this provider.
    4.  **Configuration:** Centralize settings into `config.yaml`, including the new `llm.provider` setting.
    5.  **CLI Interface:** Refactor the entry point to use `argparse` and select the LLM provider from the config.
*   **Exit Criteria:** The codebase is organized, modular, testable, and capable of supporting different LLMs through a single configuration change.

### Phase 2: Data Persistence & Warehousing
*   **Goal:** Implement the "Data Warehouse" layer to persist state and manage data artifacts effectively. This demonstrates a key Data Engineering competency.
*   **Key Tasks:**
    1.  **Schema Implementation:** Use SQLAlchemy to define and create the SQLite database schema (`Lessons`, `Assets`, `Quizzes`, `Questions`, `Feedback_Logs`).
    2.  **Integrate Ingestion:** Modify the Ingestion Silo to write extracted text and image metadata into the database.
    3.  **Stateful Processing:** The Orchestrator will now read/write job status to the `Quizzes` table.
    4.  **Artifact Storage:** Generated questions will be stored in the `Questions` table, associated with a specific quiz run.
*   **Exit Criteria:** The application is no longer stateless. All inputs, outputs, and intermediate states are tracked in the database, providing an audit trail.

### Phase 3: Activating the Agentic Workflow
*   **Goal:** Implement the core multi-agent "critique loop" to showcase autonomous decision-making and quality control.
*   **Key Tasks:**
    1.  **Implement Analyst Agent:** The Analyst Agent processes the `Retake` PDF and generates a "Style Profile" which is saved to the database.
    2.  **Implement Generator/Critic Loop:**
        *   The Generator creates a draft quiz based on the Style Profile and Lesson Context.
        *   The Critic agent validates the draft against the `qa_guidelines.txt`.
        *   If the draft is flawed, the Critic returns detailed feedback, and the Generator attempts a revision. This loop continues until the Critic approves.
    3.  **Orchestration Logic:** Implement the state machine (using LangGraph or a custom loop) that manages the Generator -> Critic -> Generator flow.
*   **Exit Criteria:** The system can autonomously generate and refine a quiz until it meets a defined quality bar, demonstrating a true agentic system.

### Phase 4: Human-in-the-Loop (Teacher Feedback)
*   **Goal:** Introduce the interactive feedback session for the teacher.
*   **Key Tasks:**
    1.  **Feedback Interface:** Create a simple terminal-based interface that:
        *   Presents the approved quiz from Phase 3.
        *   Allows the teacher to "accept", "reject", or "request changes" on a per-question basis.
    2.  **Feedback Persistence:** Teacher feedback is logged in the `Feedback_Logs` table.
    3.  **Re-generation Trigger:** If changes are requested, a new task is sent to the Orchestrator to re-run the Generator agent with the new feedback as additional context.
*   **Exit Criteria:** The application supports a full, iterative workflow where the teacher's expertise guides the final output.

---

## 3. Timeline & Milestones

*   **Phase 1:** Estimated 2-3 work sessions.
*   **Phase 2:** Estimated 3-4 work sessions.
*   **Phase 3:** Estimated 4-5 work sessions.
*   **Phase 4:** Estimated 2-3 work sessions.

This roadmap provides a structured approach to building a portfolio piece that is not just a demo, but a well-architected example of a modern AI-powered data application.
