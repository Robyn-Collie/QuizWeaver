# Implementation Roadmap: QuizWeaver

**Version:** 1.4
**Status:** Planning

---

## 1. Objective

This roadmap outlines the phased development plan to transition **QuizWeaver** from a single script proof-of-concept into a robust, agentic pipeline. Each phase is designed to deliver a discrete set of functionalities, culminating in a production-ready system that showcases advanced data engineering and Agentic AI principles.

---

## 2. Development Phases

### Phase 1: Foundational Refactoring & Quality Gates
*   **Goal:** Deconstruct the monolithic `main.py` into a clean, modular architecture, introduce an LLM abstraction layer, and establish automated quality gates.
*   **Key Tasks:**
    1.  **Modularize Codebase:** Refactor all functionality into the `src` directory with distinct modules.
    2.  **Implement LLM Abstraction:** Create the `src/llm_provider.py` to make the application LLM-agnostic.
    3.  **Centralize Configuration:** Use `config.yaml` to manage all settings.
    4.  **Write Unit Tests:** Create a `tests/` directory and implement initial unit tests for the refactored modules using `pytest`.
    5.  **Set Up Pre-Commit Hooks:** Configure `pre-commit` to automatically run linters (`ruff`) and `pytest` before each commit.
*   **Exit Criteria:** The codebase is organized, modular, testable, and protected by automated quality checks.

### Phase 1.5: Continuous Integration (CI)
*   **Goal:** Implement a CI pipeline to automatically validate changes.
*   **Key Tasks:**
    1.  **Create GitHub Actions Workflow:** Set up a `.github/workflows/ci.yml` file.
    2.  **Automate Testing:** Configure the workflow to run the full `pytest` suite on every push and pull request.
*   **Exit Criteria:** The project has an automated CI pipeline.

### Phase 2: Data Persistence & Workflow Refinement
*   **Goal:** Implement the "Data Warehouse" layer and refine the user workflow.
*   **Key Tasks:**
    1.  **Schema Implementation:** Use SQLAlchemy to define and create the SQLite database.
    2.  **Refactor CLI for Workflow:** Update `main.py` to use `argparse` sub-commands (`ingest`, `generate`) to separate the ingestion and generation workflows.
    3.  **Integrate Ingestion:** Modify the Ingestion Silo to write data to the database, triggered by the `ingest` command.
    4.  **Stateful Generation:** The `generate` command will create a new `Quiz` record and associate `Question` records with it.
*   **Exit Criteria:** The application is no longer stateless and provides a clear, efficient CLI workflow for the user.

### Phase 2.5: Multimodal Ingestion Upgrade
*   **Goal:** Leverage a powerful multimodal model (e.g., Gemini 3 Pro) to perform intelligent document layout analysis.
*   **Key Tasks:**
    1.  **Implement `Gemini3ProProvider`:** Create a new provider in `src/llm_provider.py` for the new model.
    2.  **Develop "Intelligent Ingestion" Workflow:** Create a new function in `src/ingestion.py` that sends PDF pages as images to the provider to get a structured analysis of the layout.
    3.  **Update Database:** Enhance the database schema to store this new, rich, structured content.
*   **Exit Criteria:** The application can understand the relationship between text and images in source documents.

### Phase 3: Activating the Agentic Workflow
*   **Goal:** Implement the core multi-agent "critique loop" based on a formal rubric.
*   **Key Tasks:**
    1.  **Create Evaluation Rubric:** Author `Project_Planning/04_Evaluation_Rubric.md`.
    2.  **Refine Critic Agent:** Update the Critic Agentï¿½s prompt and logic to strictly enforce the new rubric.
    3.  **Orchestration Logic:** Implement the state machine (e.g., LangGraph) for the Generator -> Critic feedback loop.
*   **Exit Criteria:** The systemï¿½s QA process is guided by a documented, educationally-sound standard.

### Phase 4: Human-in-the-Loop (Teacher Feedback)
*   **Goal:** Introduce the interactive feedback session.
*   **Key Tasks:**
    1.  **Feedback Interface:** Create a simple terminal-based interface for teacher input.
    2.  **Feedback Persistence:** Log teacher feedback to the database.
    3.  **Re-generation Trigger:** Enable the Orchestrator to re-run generation based on feedback.
*   **Exit Criteria:** The application supports a full, iterative workflow guided by the end-user.

### Phase 5: Packaging & Distribution
*   **Goal:** Package the application for easy distribution.
*   **Key Tasks:**
    1.  **Create Dockerfile:** Write a `Dockerfile` to containerize the application.
    2.  **Document Usage:** Add instructions to the `README.md` on how to build and run the application using Docker.
*   **Exit Criteria:** The application is easily runnable on any system with Docker.

---

## 3. Timeline & Milestones

*   **Phase 1 & 1.5:** Estimated 3-4 work sessions.
*   **Phase 2 & 2.5:** Estimated 4-5 work sessions.
*   **Phase 3:** Estimated 4-5 work sessions.
*   **Phase 4:** Estimated 2-3 work sessions.
*   **Phase 5:** Estimated 1-2 work sessions.
