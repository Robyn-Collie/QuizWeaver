# QuizWeaver

**Open-source, privacy-first AI teaching platform for educators.**

QuizWeaver helps teachers generate curriculum-aligned quizzes, study materials, rubrics, and scaffolded variants — all from their actual lesson content. It uses a multi-agent AI pipeline with human-in-the-loop review, ensuring teachers stay in control while saving hours of assessment preparation time.

> QuizWeaver is teacher-facing only. Student work never touches AI providers. Teachers generate; students receive.

---

## Principles

QuizWeaver is built on research-backed principles for responsible AI use in education:

1. **Human-in-the-Loop** -- Teachers review and approve all AI-generated content before it reaches students. AI assists; teachers decide. *(U.S. Dept. of Education, 2023; UNESCO, 2024)*

2. **Glass Box, Not Black Box** -- Teachers see which lessons informed a quiz, what cognitive levels were targeted, and how questions were generated. No hidden algorithms. *(Khosravi et al., 2022)*

3. **Deterministic Layers** -- Standards alignment, cognitive frameworks (Bloom's, DOK), and rubric criteria are rule-based, not AI-generated. AI operates within teacher-defined constraints. *(ISTE Standards, 2024)*

4. **Verification Over Trust** -- AI output is a draft, not a deliverable. The UI encourages editing, regeneration, and critical review at every step. *(Digital Promise, 2024)*

5. **Privacy by Design** -- Local-first architecture (SQLite). No cloud dependencies for core functionality. No student PII in AI prompts. *(UNESCO, 2024)*

6. **Student Data Protection** -- Student work (essays, answers, writing samples) is NEVER sent to AI providers. No feature creates a path -- even an accidental one -- for student content to reach third-party APIs. *(FERPA, 20 U.S.C. 1232g)*

7. **Cost Transparency** -- Teachers see exactly what AI calls cost and can control spending. Mock mode enables full exploration at zero cost. *(Digital Promise, 2024)*

8. **Equity & Access** -- Works with any LLM provider including free/local models (Ollama). Reading-level variants and scaffolded content support diverse learners. *(ISTE, 2024; UNESCO, 2024)*

### Cited Sources
- [UNESCO (2024). AI Competency Framework for Teachers](https://www.unesco.org/en/articles/ai-competency-framework-teachers)
- [U.S. Dept. of Education (2023). AI and the Future of Teaching and Learning](https://www.ed.gov/sites/ed/files/documents/ai-report/ai-report.pdf)
- [ISTE (2024). Standards for Educators](https://iste.org/standards/educators)
- [Digital Promise (2024). AI Literacy Framework](https://digitalpromise.org/2024/06/18/ai-literacy-a-framework-to-understand-evaluate-and-use-emerging-technology/)
- [Khosravi et al. (2022). Explainable AI in Education](https://www.sciencedirect.com/science/article/pii/S2666920X22000297)

---

## Features

### Assessment Generation
- **AI Quiz Generation** -- Multi-agent pipeline (Generator + Critic) produces quality questions aligned to your taught content
- **Cognitive Frameworks** -- Bloom's Taxonomy and Webb's DOK with configurable distribution across cognitive levels
- **Standards Alignment** -- Searchable standards database (Virginia SOL) with autocomplete picker
- **Topic-Based Generation** -- Generate quizzes from specific topics without a source quiz
- **Question Bank** -- Save and reuse favorite questions across quizzes

### Study Materials
- **Flashcards** -- AI-generated with inline editing, Anki-compatible TSV export
- **Study Guides** -- Comprehensive review materials from lesson content
- **Vocabulary Lists** -- Key terms with definitions and context
- **Review Sheets** -- Quick-reference summaries for test preparation

### Differentiation
- **Reading-Level Variants** -- ELL, below grade, on grade, and advanced versions of any quiz
- **Rubric Generation** -- Standards-aligned rubrics with proficiency levels (Beginning through Advanced)
- **Scaffolded Content** -- Adjusted complexity while maintaining assessment rigor

### Performance Analytics
- **Gap Analysis** -- Compare assumed knowledge (from lessons) to actual performance
- **Standards Mastery** -- Track progress toward curriculum standards
- **Trend Analysis** -- Visualize performance over time
- **Re-teach Suggestions** -- AI-generated recommendations based on identified gaps

### Export Formats
- **PDF** -- Print-ready quizzes and study materials
- **DOCX** -- Editable Word documents with answer keys
- **CSV** -- Spreadsheet-compatible data export
- **GIFT** -- Moodle-compatible quiz import format
- **TSV** -- Anki-compatible flashcard export

### Teacher Tools
- **Class Sections & Organization** -- Separate lesson histories, quizzes, and analytics per class/block
- **Lesson Tracking** -- Log lessons with automatic topic extraction and knowledge depth tracking
- **Cost Tracking** -- Per-action and per-provider cost breakdowns with budget thresholds
- **Dark Mode** -- Full dark theme with WCAG AA compliant contrast
- **Keyboard Shortcuts** -- Chord-based navigation (press `?` for help)

### AI Literacy
- **Contextual Tooltips** -- Inline explanations of AI concepts throughout the UI
- **Confidence Banners** -- Every AI-generated output is labeled as a draft requiring review
- **Privacy Notices** -- Clear disclosure of what data is sent to AI providers
- **Help Section** -- Dedicated AI literacy section with cited educational research

---

## Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Run the Web Interface

```bash
python -c "
import yaml
with open('config.yaml') as f:
    config = yaml.safe_load(f)
from src.web.app import create_app
app = create_app(config)
app.run(debug=True)
"
```

Open http://localhost:5000 -- the onboarding wizard will guide you through creating your first class.

### Run Tests

```bash
python -m pytest       # 1078 tests, all passing
```

### Docker

```bash
docker-compose up
```

---

## LLM Providers

QuizWeaver is LLM-agnostic. Choose the provider that fits your needs and budget:

| Provider | Cost | Privacy | Setup |
|----------|------|---------|-------|
| **Mock** (default) | Free | No data sent anywhere | None -- works out of the box |
| **Ollama** (local) | Free | Data stays on your machine | Install [Ollama](https://ollama.com), pull a model |
| **Google Gemini** | Pay-per-use | Data sent to Google | [Get API key](https://aistudio.google.com) |
| **OpenAI** | Pay-per-use | Data sent to OpenAI | [Get API key](https://platform.openai.com) |
| **Any OpenAI-compatible API** | Varies | Varies | Configure base URL + key |

The built-in **Provider Setup Wizard** (Settings > Setup Wizard) walks you through configuration step by step, including cost implications and privacy considerations.

### Mock Provider (Default -- Zero Cost)

```yaml
# config.yaml
llm:
  provider: "mock"
```

Mock mode produces placeholder content for exploring all features at zero cost. No API key needed.

---

## Architecture

```
Web Dashboard (Flask)  /  CLI (main.py)
         |
    +---------+---------+
    |         |         |
Classroom  Lesson    Standards
 Manager   Tracker   Database
    |         |         |
    +----+----+---------+
         |
    Quiz Generator / Study Generator / Variant Generator / Rubric Generator
         |
    Agentic Pipeline (Generator + Critic)
         |
    LLM Provider (Mock | Gemini | OpenAI | Ollama | Vertex AI)
         |
    Cost Tracking
         |
    Export (PDF | DOCX | CSV | GIFT | TSV)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system diagram.

---

## Project Structure

```
QuizWeaver/
├── main.py                    # CLI entry point
├── config.yaml                # Application configuration
├── requirements.txt           # Python dependencies
│
├── src/
│   ├── classroom.py           # Class sections CRUD (create, list, update, delete)
│   ├── lesson_tracker.py      # Lesson logging, topic extraction, knowledge tracking
│   ├── quiz_generator.py      # Quiz generation orchestration
│   ├── study_generator.py     # Flashcards, study guides, vocabulary, review sheets
│   ├── variant_generator.py   # Reading-level variants (ELL, below/on/advanced)
│   ├── rubric_generator.py    # Standards-aligned rubric generation
│   ├── topic_generator.py     # Topic-based generation (no source quiz needed)
│   ├── question_regenerator.py # Individual question regeneration
│   ├── agents.py              # Agentic pipeline (Generator, Critic, Orchestrator)
│   ├── cognitive_frameworks.py # Bloom's, DOK, question type definitions
│   ├── standards.py           # Standards database CRUD and search
│   ├── cost_tracking.py       # API cost logging, rate limits, budget thresholds
│   ├── performance_import.py  # CSV upload and quiz score entry
│   ├── performance_analytics.py # Gap analysis, trends, mastery tracking
│   ├── reteach_generator.py   # AI-generated re-teach suggestions
│   ├── export.py              # CSV, DOCX, GIFT export
│   ├── study_export.py        # Flashcard TSV/CSV, study material PDF/DOCX
│   ├── rubric_export.py       # Rubric CSV, DOCX, PDF
│   ├── database.py            # SQLAlchemy ORM models
│   ├── migrations.py          # Idempotent database migration runner
│   ├── llm_provider.py        # LLM abstraction (Mock, Gemini, OpenAI, Vertex, Ollama)
│   ├── mock_responses.py      # Fabricated LLM responses for development
│   └── web/
│       ├── app.py             # Flask application factory
│       ├── routes.py          # Web route handlers
│       ├── auth.py            # User authentication
│       ├── config_utils.py    # Configuration save helper
│       └── tooltip_data.py    # AI literacy tooltip content
│
├── tests/                     # 1078 tests (pytest)
├── templates/                 # Jinja2 HTML templates
├── static/                    # CSS, JavaScript, static assets
├── migrations/                # SQL migration scripts (001-008)
├── data/                      # Standards database (sol_standards.json)
├── prompts/                   # Agent system prompts
└── docs/
    ├── ARCHITECTURE.md        # System architecture
    ├── BACKLOG.md             # Feature backlog with principles
    ├── COMPETITIVE_ANALYSIS.md # EdTech landscape research
    ├── COST_STRATEGY.md       # Cost control approach
    └── ROADMAP.md             # Development roadmap
```

---

## Web Routes

| Route | Description |
|-------|-------------|
| `/dashboard` | Tool-oriented landing page with classes, activity feed |
| `/classes` | List all classes with lesson/quiz stats |
| `/classes/<id>` | Class detail with knowledge depth, lessons, quizzes |
| `/generate` | Generate a quiz for a class |
| `/generate/topics` | Generate from specific topics |
| `/quizzes` | Browse all quizzes with search and filtering |
| `/quizzes/<id>` | Quiz detail with inline editing |
| `/study/generate` | Generate study materials (flashcards, guides, vocabulary, review sheets) |
| `/study` | Browse study materials |
| `/question-bank` | Save, browse, and search favorite questions |
| `/standards` | Browse and search standards database |
| `/analytics` | Performance analytics and gap analysis |
| `/costs` | API cost tracking with budget thresholds |
| `/settings` | LLM provider configuration and testing |
| `/settings/wizard` | Guided provider setup with AI literacy context |
| `/help` | User guide with AI literacy education section |

---

## Development

### Key Rules

1. **Always use MockLLMProvider** during development (`llm.provider: "mock"`)
2. **Never send student work to AI providers** -- QuizWeaver is teacher-facing only
3. **Test-Driven Development** -- Write tests before implementation
4. **Local-First** -- SQLite + file-based config, no cloud dependencies
5. **Teacher-in-Control** -- All AI outputs are drafts requiring teacher approval

### Database

8 migration scripts, idempotent (safe to run multiple times):

| Table | Purpose |
|-------|---------|
| `classes` | Teacher classes/blocks |
| `lesson_logs` | Lessons taught per class |
| `quizzes` | Generated quizzes (with variant/parent tracking) |
| `questions` | Individual quiz questions |
| `rubrics` / `rubric_criteria` | Standards-aligned rubrics |
| `performance_data` | Anonymized student performance |
| `standards` | Curriculum standards database |
| `question_bank` | Saved/favorite questions |
| `users` | Teacher authentication |

---

## Contributing

QuizWeaver follows strict principles for responsible AI in education. Before contributing, please read:

- **[CLAUDE.md](CLAUDE.md)** -- Development principles and guidelines
- **[docs/BACKLOG.md](docs/BACKLOG.md)** -- Feature backlog with Student Data Protection principle
- **[docs/COMPETITIVE_ANALYSIS.md](docs/COMPETITIVE_ANALYSIS.md)** -- EdTech landscape research

Key contribution guidelines:
- All AI-generated content must be labeled as drafts requiring teacher review
- No feature may send student work to cloud AI providers
- New LLM features must work with MockLLMProvider at zero cost
- Test coverage is required (1078+ tests currently passing)

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
