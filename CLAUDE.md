# QuizWeaver - AI-Powered Teaching Platform

## Project Overview

QuizWeaver is an AI-powered teaching assistant platform that helps educators manage their entire teaching workflow—from lesson planning and progress tracking to assessment generation and performance analytics.

Originally a quiz retake generator, QuizWeaver is expanding into a comprehensive platform that:
- Tracks what's been taught across multiple classes/blocks
- Monitors student progress toward standards (SOL, SAT, school initiatives)
- Analyzes performance gaps between assumed and actual learning
- Automates administrative burden while keeping teachers firmly in control
- Protects student privacy through anonymization
- **Minimizes cost through mock LLM providers during development**

## Tech Stack

- **Language**: Python 3.9+
- **Database**: SQLite (local-first, no server needed)
- **ORM**: SQLAlchemy with declarative models
- **CLI Framework**: argparse
- **LLM Providers**:
  - Google Gemini (via google-generativeai)
  - Google Vertex AI (via google-cloud-aiplatform)
  - **MockLLMProvider** (zero-cost development mode)
- **Testing**: pytest
- **Output Formats**:
  - PDF generation (reportlab)
  - QTI packages (Canvas-compatible)
  - Vertex AI Imagen (image generation)

## Critical Development Rules

### 🚨 COST CONTROL - MOST IMPORTANT 🚨

1. **ALWAYS use MockLLMProvider during development**
   - Default in config.yaml: `llm.provider: "mock"`
   - Zero cost, fabricated responses for testing
   - NEVER change to real provider without explicit permission

2. **Real API calls require user approval**
   - The `get_provider()` function has a built-in approval gate
   - User must type "yes" to proceed with real APIs
   - Cost warnings are displayed before any real API call

3. **Document cost implications**
   - Any new feature using LLMs must document estimated cost
   - Include cost estimates in proposals and specs
   - Use cost tracking infrastructure (Phase 1, Section 6)

### Development Guidelines

- **Test-Driven Development**: Write tests before implementation
- **Backward Compatibility**: Existing quiz generation must continue working
- **Multi-Class Isolation**: Thoroughly test that classes don't leak data
- **Idempotent Migrations**: Database migrations must be safe to run multiple times
- **Privacy-First**: All student data is anonymized
- **Teacher-in-Control**: All AI-generated content requires teacher approval

### Security & Compliance

- **GDPR Compliance**: Student data handling must comply with privacy regulations
- **Security-First Design**: Validate inputs, sanitize outputs, prevent injection
- **Local-First**: No cloud dependencies for core functionality (SQLite, not cloud DB)
- **Anonymization**: PII scrubbing utilities for all student data

## How to Run

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Verify database schema (runs migrations if needed)
python -c "from src.migrations import initialize_db; initialize_db('quiz_warehouse.db')"
```

### Running the Application

```bash
# Ingest content from documents
python main.py ingest

# Generate quiz (uses MockLLMProvider by default)
python main.py generate

# Generate quiz with specific parameters
python main.py generate --count 20 --grade "8th Grade" --sol "SOL 8.1" "SOL 8.2"

# Skip interactive review
python main.py generate --no-interactive
```

### Running Tests

```bash
# Run all tests with pytest
python -m pytest

# Run specific test file
python tests/test_mock_provider_simple.py
python tests/test_database_schema.py

# Run with verbose output
python -m pytest -v
```

## Project Structure

```
QuizWeaver/
├── main.py                 # CLI entry point (argparse commands)
├── config.yaml             # Application configuration
├── requirements.txt        # Python dependencies
│
├── src/                    # Source code
│   ├── agents.py           # Agentic pipeline (Analyst, Generator, Critic)
│   ├── classroom.py        # Multi-class management (Phase 1, Section 3)
│   ├── lesson_tracker.py   # Lesson logging & assumed knowledge (Phase 1, Section 4)
│   ├── database.py         # SQLAlchemy ORM models
│   ├── migrations.py       # Database migration runner
│   ├── llm_provider.py     # LLM provider abstraction (includes MockLLMProvider)
│   ├── mock_responses.py   # Fabricated LLM responses for development
│   ├── ingestion.py        # Content ingestion (PDF, DOCX, multimodal)
│   ├── image_gen.py        # Image generation (Vertex Imagen)
│   ├── output.py           # PDF and QTI export
│   └── review.py           # Human-in-the-loop review interface
│
├── tests/                  # Unit and integration tests
│   ├── test_mock_provider_simple.py
│   ├── test_database_schema.py
│   └── ...
│
├── migrations/             # SQL migration scripts
│   └── 001_add_classes.sql
│
├── prompts/                # Agent system prompts
│   ├── analyst_prompt.txt
│   ├── generator_prompt.txt
│   └── critic_prompt.txt
│
├── openspec/               # OpenSpec spec-driven development
│   ├── config.yaml         # OpenSpec configuration
│   ├── specs/              # Main specifications (source of truth)
│   ├── changes/            # Active changes (feature branches)
│   └── archive/            # Completed changes
│
├── Content_Summary/        # Input: Lesson content
├── Retake/                 # Input: Original quiz for style analysis
├── Quiz_Output/            # Output: Generated quizzes (PDF, QTI)
├── extracted_images/       # Extracted images from PDFs
└── generated_images/       # AI-generated images (Vertex Imagen)
```

## Key Modules

### Agentic Pipeline (src/agents.py)

Three-agent system for quiz generation:
1. **Analyst Agent**: Analyzes original quiz style, determines question count and image ratio
2. **Generator Agent**: Creates questions matching the style profile
3. **Critic Agent**: Reviews questions for quality, alignment, and appropriateness

All agents use the LLM provider abstraction (MockLLMProvider during development).

### LLM Provider Abstraction (src/llm_provider.py)

- `LLMProvider` base class: Common interface for all providers
- `GeminiProvider`: Google Gemini API (real cost)
- `VertexAIProvider`: Google Vertex AI (real cost)
- `MockLLMProvider`: **Zero-cost fabricated responses for development**
- `get_provider(config)`: Factory function with approval gate

### Database (src/database.py)

SQLAlchemy ORM models:
- `Lesson`: Ingested lesson content
- `Asset`: Extracted images from lessons
- `Class`: Teacher's class/block (multi-class support)
- `LessonLog`: Tracks lessons taught to each class
- `Quiz`: Generated quizzes
- `Question`: Individual quiz questions
- `FeedbackLog`: Human and AI feedback
- `PerformanceData`: Student performance (Phase 2)

### Migrations (src/migrations.py)

- Idempotent migration runner (safe to run multiple times)
- Detects missing tables and applies migrations
- Creates default "Legacy Class" for backward compatibility
- SQL scripts in `migrations/` directory

## Development Workflow

### Using OpenSpec (Spec-Driven Development)

OpenSpec is used for structured, parallelizable development:

```bash
# List active changes
openspec list

# View change status
openspec status --change teaching-platform-expansion

# Apply tasks (implement a change)
/opsx:apply teaching-platform-expansion

# Archive completed change
/opsx:archive teaching-platform-expansion
```

### OpenSpec Workflow

1. **Proposal**: High-level vision and scope
2. **Specs**: Detailed specifications (delta specs for changes)
3. **Design**: Architectural decisions and trade-offs
4. **Tasks**: Granular implementation tasks (max 2 hours each)
5. **Implementation**: Execute tasks, mark complete
6. **Archive**: Update main specs, archive change

### Making Changes

1. Start with a brain dump (dictate requirements)
2. Claude creates proposal → specs → design → tasks
3. Review and refine each artifact
4. Implement tasks incrementally
5. Test each section before moving on
6. Commit frequently with clear messages

## Current Status

**Phase**: Platform Expansion (Phase 1 - Foundation)
**Active Change**: teaching-platform-expansion
**Progress**: 13/59 tasks complete (22%)

### Completed Sections

- ✅ **Section 1: MockLLMProvider Implementation** (5/5 tasks)
  - Zero-cost development mode
  - Mock responses for Analyst, Generator, Critic
  - User approval gate for real API calls
  - All tests passing

- ✅ **Section 2: Database Schema Extension** (4/4 tasks)
  - Multi-class support (Classes, LessonLogs tables)
  - Idempotent migrations
  - SQLAlchemy ORM models
  - All tests passing

### Next Section

- ⏳ **Section 3: Multi-Class Management Module** (0/6 tasks)
  - Create `src/classroom.py` module
  - Add CLI commands (new-class, list-classes, set-class)
  - Implement class management handlers
  - Test multi-class functionality

## Common Tasks

### Adding a New CLI Command

1. Add subparser in `main.py` under `# --- <Command> Command ---`
2. Define handler function `handle_<command>(config, args)`
3. Route to handler in `if args.command == "<command>":` block
4. Test manually and write unit tests

### Adding a New Database Model

1. Define model class in `src/database.py` (inherit from `Base`)
2. Create migration SQL in `migrations/XXX_description.sql`
3. Run migrations: `python -c "from src.migrations import initialize_db; initialize_db('quiz_warehouse.db')"`
4. Write tests in `tests/test_database_schema.py`

### Adding a New Agent Prompt

1. Create prompt file in `prompts/<agent>_prompt.txt`
2. Reference in `config.yaml` under `prompts` section
3. Load in `src/agents.py` using `open(prompt_file).read()`
4. Test with MockLLMProvider first

### Testing a New Feature

1. Write unit test in `tests/test_<feature>.py`
2. Use temporary databases for DB tests (avoid modifying quiz_warehouse.db)
3. Mock LLM providers (use MockLLMProvider)
4. Run tests: `python -m pytest tests/test_<feature>.py -v`

## Known Issues / Edge Cases

### Windows-Specific

- **Unicode encoding**: Use `[PASS]`, `[FAIL]`, `[OK]` instead of ✓, ✗, ✅
- **File locking**: Windows locks SQLite DBs aggressively; use `engine.dispose()` before cleanup
- **Bash commands**: Use Git Bash or WSL; PowerShell has different syntax

### Database

- **Class ID on existing quizzes**: Migration creates "Legacy Class" and assigns old quizzes to it
- **Duplicate migration runs**: Migrations are idempotent but check for "duplicate column" errors

### Cost Control

- **Accidental real API calls**: `get_provider()` has approval gate, but always verify config.yaml
- **Cost tracking not yet implemented**: Section 6 will add cost logging and limits

## Naming Conventions

- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions**: `snake_case()`
- **Constants**: `UPPER_SNAKE_CASE`
- **CLI commands**: `kebab-case` (e.g., `new-class`, `list-classes`)
- **Database tables**: `snake_case` (e.g., `lesson_logs`, `performance_data`)

## Git Workflow

- **Branch strategy**: Work on `main` (small project)
- **Commit messages**: Descriptive, imperative mood (e.g., "Add multi-class management CLI")
- **Co-authoring**: Add `Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>`
- **Commit frequency**: After each section or major feature
- **Push regularly**: Share progress with team/workshop

## Documentation

- **Update README.md**: When adding major features
- **Inline comments**: For complex logic, not obvious code
- **Docstrings**: For public functions and classes
- **OpenSpec artifacts**: Keep proposal, specs, design, tasks up to date

## Contact / Support

- **Instructor**: Liz Howard (Agentic SDLC Intensive)
- **Project Repo**: QuizWeaver (local project)
- **OpenSpec**: https://github.com/Fission-AI/OpenSpec/

## Quick Reference

```bash
# Run tests
python -m pytest

# Generate quiz (mock mode)
python main.py generate

# OpenSpec status
openspec status --change teaching-platform-expansion

# Install dependencies
pip install -r requirements.txt

# Run migrations
python -c "from src.migrations import initialize_db; initialize_db('quiz_warehouse.db')"
```

---

**Remember**: When in doubt, use MockLLMProvider. Avoid real API costs during development.
