# Development Practices & Philosophy

**Version:** 1.0
**Status:** Adopted

---

## 1. Purpose

This document codifies the development practices and quality standards for the Quiz Retake Generator project. It serves as a central reference for ensuring that the project is not only functional but also well-engineered, maintainable, and secure. Adherence to these practices is a core component of the "Staff Engineer" level of quality this project aims to exhibit.

---

## 2. Code Quality & Automation

### 2.1 Linting & Formatting
*   **Tooling:** We use `ruff` for both linting (identifying potential errors and bad patterns) and code formatting.
*   **Enforcement:** Code style is not optional. It is automatically enforced by a pre-commit hook. Any code that does not meet the style guide will be automatically reformatted or the commit will be blocked.

### 2.2 Pre-Commit Hooks
*   **Framework:** We use the `pre-commit` framework to manage local Git hooks.
*   **Configuration:** The configuration is defined in `.pre-commit-config.yaml`.
*   **Function:** Before any commit is accepted, a series of automated checks are run locally, including:
    1.  Code formatting (`ruff format`)
    2.  Linting (`ruff`)
    3.  Unit testing (`pytest`)
*   **Philosophy:** This enforces quality at the source. No failing test or poorly formatted code should ever enter the main branch.

---

## 3. Testing Strategy

### 3.1 Unit Testing
*   **Framework:** `pytest` is our chosen framework for writing and running unit tests.
*   **Location:** All tests are located in the `tests/` directory, mirroring the structure of the `src/` directory.
*   **Principle:** Every module and significant function should have corresponding unit tests. The tests ensure that the individual components of the application work as expected in isolation.

### 3.2 Continuous Integration (CI)
*   **Platform:** We use GitHub Actions for our CI pipeline.
*   **Workflow:** The workflow, defined in `.github/workflows/ci.yml`, is triggered on every push and pull request to the `main` branch.
*   **Function:** The CI pipeline automatically:
    1.  Checks out the code.
    2.  Installs all dependencies.
    3.  Runs the full `pytest` suite.
*   **Philosophy:** This provides a second, authoritative layer of quality assurance. It guarantees that the project remains in a working state at all times.

---

## 4. Architecture & Extensibility

### 4.1 Modular, Silo-Based Design
*   The application is built on a "silo" architecture, where each major function (ingestion, agentic logic, output) is decoupled into its own module. This is detailed in the `01_System_Architecture.md` document.
*   **Benefit:** This makes the system easier to understand, maintain, and test.

### 4.2 LLM-Agnostic Design
*   The application is not tied to a single AI provider. Through the **LLM Provider Abstraction Layer** (`src/llm_provider.py`), we can easily switch between different language models (Gemini, OpenAI, etc.) with a simple configuration change.
*   **Benefit:** This future-proofs the application and allows for cost and performance optimization.

### 4.3 Extensibility via MCPs (Multi-Capability Providers)
*   **Philosophy:** We recognize that this application can be made more powerful by integrating with external tools and services. The architecture is designed to accommodate this through MCPs.
*   **Future Use Cases:** As detailed in the architecture document, potential MCPs could provide services for:
    *   **Curriculum Standard Lookups:** Automatically fetching SOL standards from official sources.
    *   **Advanced Image Analysis:** Understanding the content of diagrams to ask better questions.
    *   **Plagiarism Detection:** Ensuring the novelty of generated questions by searching for them online.
*   **Benefit:** This demonstrates a forward-thinking approach, planning for how the application can evolve and integrate into a larger ecosystem of tools.

---

## 5. Version Control

*   **Commit Messages:** All commit messages MUST follow the [Conventional Commits](https://www.conventionalcommits.org/) specification (e.g., `feat:`, `fix:`, `docs:`, `chore:`). This is enforced by `.clinerules`.
*   **Branching Strategy:** We follow a `main`-branch workflow. New features or fixes should be developed on separate branches (`feature/name`, `fix/issue`) and merged into `main` via pull requests (when collaborating).
