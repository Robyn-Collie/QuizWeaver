# QuizWeaver - AI-Powered Teaching Platform

QuizWeaver is an AI-powered teaching assistant that helps educators manage classes, track lessons, and generate curriculum-aligned assessments. It features a multi-agent quiz generation pipeline, a CLI interface, and a web dashboard.

---

## Features

- **Multi-Class Management** -- Create and manage multiple class blocks with independent lesson histories
- **Lesson Tracking** -- Log lessons with automatic topic extraction and assumed knowledge depth tracking (1-5 scale)
- **AI Quiz Generation** -- Three-agent pipeline (Generator, Critic, Orchestrator) produces quality questions
- **Web Dashboard** -- Flask-based UI for managing classes, lessons, quizzes, and viewing cost reports
- **Cost Control** -- MockLLMProvider for zero-cost development; approval gate for real API calls
- **Multiple Output Formats** -- PDF preview and Canvas-compatible QTI packages
- **Local-First** -- SQLite database, no cloud dependencies for core functionality

---

## Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Initialize Database

```bash
python -c "from src.migrations import init_database_with_migrations; init_database_with_migrations('quiz_warehouse.db')"
```

### Run Tests

```bash
python -m pytest -v
```

---

## CLI Commands

### Content & Quiz Generation

```bash
# Ingest content from Content_Summary/ directory
python main.py ingest

# Generate a quiz (uses MockLLMProvider by default -- zero cost)
python main.py generate

# Generate with specific parameters
python main.py generate --count 20 --grade "8th Grade" --sol "SOL 8.1" "SOL 8.2"

# Generate for a specific class (overrides active class)
python main.py generate --class 2

# Skip interactive review
python main.py generate --no-interactive
```

### Class Management

```bash
# Create a new class
python main.py new-class --name "7th Grade Science - Block A" --grade "7th Grade" --subject "Science"

# Create with standards
python main.py new-class --name "8th Grade Bio" --grade "8th Grade" --subject "Biology" --standards "SOL 8.1,SOL 8.2"

# List all classes
python main.py list-classes

# Set the active class (used as default for other commands)
python main.py set-class 2
```

### Lesson Tracking

```bash
# Log a lesson with inline text
python main.py log-lesson --text "Today we covered photosynthesis and the light reactions"

# Log a lesson from a file
python main.py log-lesson --file lesson_notes.txt

# Log with manual topic override and notes
python main.py log-lesson --text "Cell division review" --topics "mitosis,meiosis" --notes "Students struggled with metaphase"

# Log to a specific class
python main.py log-lesson --class 3 --text "Introduction to genetics"

# List lessons for the active class
python main.py list-lessons

# Filter lessons
python main.py list-lessons --last 7            # Last 7 days
python main.py list-lessons --topic "photosynthesis"
python main.py list-lessons --from 2026-01-01 --to 2026-01-31
```

### Cost Tracking

```bash
# View API cost summary (only relevant when using real LLM providers)
python main.py cost-summary
```

---

## Web Interface

QuizWeaver includes a Flask web dashboard for browser-based management.

### Running the Web Server

```bash
# Start the development server
python -c "from src.web.app import create_app; create_app().run(debug=True)"
```

Then open http://localhost:5000 in your browser.

### Web Pages

| Route | Description |
|-------|-------------|
| `/dashboard` | Overview with class, lesson, and quiz counts |
| `/classes` | List all classes with lesson/quiz stats |
| `/classes/new` | Create a new class (form) |
| `/classes/<id>` | Class detail with knowledge depth, lessons, quizzes |
| `/classes/<id>/lessons` | Lesson history for a class |
| `/classes/<id>/lessons/new` | Log a new lesson (form) |
| `/quizzes` | List all generated quizzes |
| `/quizzes/<id>` | Quiz detail with all questions |
| `/costs` | API cost tracking dashboard |

---

## Architecture

```
CLI (main.py)  /  Web (Flask)
        |
   +----+----+
   |         |
Classroom  Lesson Tracker  -->  Quiz Generator
   |         |                       |
   +----+----+              Agentic Pipeline
        |                  (Generator + Critic)
   Database (SQLite)              |
                           LLM Provider
                        (Mock | Gemini | Vertex)
                               |
                          Cost Tracking
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system diagram and module responsibilities.

### Project Structure

```
QuizWeaver/
├── main.py                 # CLI entry point
├── config.yaml             # Application configuration
├── requirements.txt        # Python dependencies
│
├── src/
│   ├── classroom.py        # Multi-class CRUD (create, get, list, delete, update)
│   ├── lesson_tracker.py   # Lesson logging, topic extraction, knowledge tracking
│   ├── quiz_generator.py   # Reusable generate_quiz() function
│   ├── agents.py           # Agentic pipeline (Generator, Critic, Orchestrator)
│   ├── cost_tracking.py    # API cost logging, rate limits, reports
│   ├── database.py         # SQLAlchemy ORM models
│   ├── migrations.py       # Idempotent database migration runner
│   ├── llm_provider.py     # LLM abstraction (Mock, Gemini, Vertex AI)
│   ├── mock_responses.py   # Fabricated LLM responses for development
│   ├── ingestion.py        # Content ingestion (PDF, DOCX, multimodal)
│   ├── image_gen.py        # Image generation (Vertex Imagen)
│   ├── output.py           # PDF and QTI export
│   ├── review.py           # Interactive review interface
│   └── web/
│       ├── app.py          # Flask application factory
│       └── routes.py       # Web route handlers
│
├── tests/                  # 160+ tests (pytest)
├── templates/              # Jinja2 HTML templates
├── static/                 # CSS and static assets
├── migrations/             # SQL migration scripts
├── prompts/                # Agent system prompts
├── docs/                   # Documentation
│   ├── ARCHITECTURE.md     # System architecture
│   ├── COST_STRATEGY.md    # Cost control approach
│   └── USER_GUIDE.md       # Teacher user guide
│
├── Content_Summary/        # Input: Lesson content files
├── Retake/                 # Input: Original quizzes for style analysis
├── Quiz_Output/            # Output: Generated PDFs and QTI packages
├── extracted_images/       # Extracted images from PDFs
└── generated_images/       # AI-generated images
```

---

## LLM Provider Configuration

QuizWeaver defaults to **MockLLMProvider** (zero cost) for development. To use a real provider:

### Mock Provider (Default -- Zero Cost)

```yaml
# config.yaml
llm:
  provider: "mock"
```

### Google Gemini

```bash
export GEMINI_API_KEY="your-api-key"
```

```yaml
llm:
  provider: "gemini"
  model_name: "gemini-2.5-flash"
  mode: "development"  # Prompts before real API calls
```

### Google Vertex AI

```bash
gcloud auth application-default login
```

```yaml
llm:
  provider: "vertex"
  vertex_project_id: "your-project-id"
  vertex_location: "us-central1"
  model_name: "gemini-2.5-flash"
  mode: "development"
```

### Cost Limits

```yaml
llm:
  max_calls_per_session: 50    # Maximum API calls before stopping
  max_cost_per_session: 5.00   # Maximum dollars before stopping
```

See [docs/COST_STRATEGY.md](docs/COST_STRATEGY.md) for detailed cost estimates.

---

## Development

### Running Tests

```bash
# Full suite
python -m pytest -v

# Specific module
python -m pytest tests/test_classroom.py -v
python -m pytest tests/test_quiz_generator.py -v

# Exclude known external-dependency failures
python -m pytest --ignore=tests/test_model_optimizer.py -v
```

### Key Development Rules

1. **Always use MockLLMProvider** during development (`llm.provider: "mock"`)
2. **Test-Driven Development** -- Write tests before implementation
3. **Backward Compatibility** -- Existing quiz generation must continue working
4. **Local-First** -- SQLite + file-based config, no cloud dependencies for core
5. **Teacher-in-Control** -- All AI-generated content requires teacher approval

### Database Schema

| Table | Purpose |
|-------|---------|
| `classes` | Teacher classes/blocks |
| `lesson_logs` | Lessons taught to each class |
| `quizzes` | Generated quiz records |
| `questions` | Individual quiz questions |
| `lessons` | Ingested content (PDFs, DOCX) |
| `assets` | Extracted images |
| `performance_data` | Student performance (Phase 2) |
| `feedback_logs` | Human and AI feedback |

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
