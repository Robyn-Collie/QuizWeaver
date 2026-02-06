# Running the QuizWeaver Demo

This guide walks you through setting up and running the QuizWeaver demo for presentations, workshops, and testing.

## Overview

QuizWeaver is an AI-powered teaching assistant platform that helps educators manage their teaching workflow—from lesson planning and progress tracking to assessment generation and performance analytics.

**Demo Highlights:**
- 291 tests passing (160 backend + 131 web/integration)
- 51+ commits of iterative, test-driven development
- 8 CLI commands + full web interface
- $0 development cost using MockLLMProvider
- Multi-class management with lesson tracking
- Cost tracking and rate limiting
- Three-agent quiz generation pipeline

## Prerequisites

### Required Software
- Python 3.9 or higher
- Git (for cloning the repository)
- Git Bash or WSL (for running bash scripts on Windows)

### Installation

1. Clone the repository (if you haven't already):
   ```bash
   git clone <repository-url>
   cd QuizWeaver
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Verify installation:
   ```bash
   python -c "import flask, sqlalchemy, pytest; print('[OK] All dependencies installed')"
   ```

## Quick Start (3 Steps)

The fastest way to get the demo running:

```bash
# Step 1: Reset database and load demo data
bash reset_demo.sh

# Step 2: Start the web application
python app.py

# Step 3: Open browser to http://localhost:5000
```

Then follow the walkthrough in `demo_data/demo_script.md` for a guided tour.

## Full Demo Setup

### Step 1: Reset the Database

The reset script creates a clean database with demo data:

```bash
bash reset_demo.sh
```

**What this does:**
- Backs up existing database with timestamp (to `backups/` folder)
- Removes old database
- Runs migrations to create fresh schema
- Loads demo data (3 classes, 12+ lessons, sample quizzes)

**Output you should see:**
```
==========================================
QuizWeaver Demo Database Reset
==========================================

[1/4] Backing up existing database...
      [OK] Backup created: backups/quiz_warehouse_20260206_143022.db
[2/4] Removing old database...
      [OK] Old database removed
[3/4] Creating fresh database schema...
      [OK] Database schema created
[4/4] Loading demo data...
      [OK] Demo data loaded

==========================================
[OK] Demo database reset complete!
==========================================
```

### Step 2: Verify Demo Data

Confirm the demo data loaded correctly:

```bash
python main.py list-classes
```

**Expected output:**
```
Classes:
  [1] Algebra I - Block A (24 students)
  [2] Algebra I - Block C (22 students)
  [3] Geometry - Block B (26 students)
```

Check lessons:
```bash
python main.py list-lessons --class-id 1
```

### Step 3: Run the Web Application

Start the Flask web server:

```bash
python app.py
```

**Expected output:**
```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
```

Open your browser to [http://localhost:5000](http://localhost:5000)

### Step 4: Follow the Demo Script

Open `demo_data/demo_script.md` for a step-by-step walkthrough of the platform's features:

1. Dashboard overview
2. Multi-class management
3. Lesson tracking
4. Quiz generation
5. Cost tracking and analytics

## Resetting the Demo Between Runs

If you want to reset to a clean state (e.g., between workshop sessions or after testing):

```bash
bash reset_demo.sh
```

This is safe to run multiple times—it always backs up before destroying data.

### Manual Reset (Without Script)

If you can't run bash scripts:

```bash
# Backup (optional)
mkdir backups
copy quiz_warehouse.db backups\quiz_warehouse_%date:~-4%%date:~4,2%%date:~7,2%.db

# Remove old database
del quiz_warehouse.db

# Create fresh database
python -c "from src.migrations import init_database_with_migrations; init_database_with_migrations('quiz_warehouse.db')"

# Load demo data
python demo_data\setup_demo.py
```

## Demo Data Details

The demo database includes:

### Classes
- **Algebra I - Block A**: 24 students, 5 lessons logged
- **Algebra I - Block C**: 22 students, 4 lessons logged
- **Geometry - Block B**: 26 students, 3 lessons logged

### Lessons
- Algebra I topics: Linear equations, graphing, systems of equations, inequalities
- Geometry topics: Basic constructions, angle relationships, triangle congruence

### Quizzes
- Sample quizzes generated with MockLLMProvider
- Demonstrates question variety and formatting
- Shows cost tracking data

### Cost Tracking
- Simulated API calls with zero real cost
- Rate limits configured (10 requests/minute)
- Cost estimates for Gemini and Vertex AI

## CLI Commands Available

The demo includes these CLI commands:

```bash
# Class management
python main.py new-class --name "Algebra I - Block A" --grade "9th Grade" --students 24
python main.py list-classes
python main.py set-class 1

# Lesson tracking
python main.py log-lesson --class-id 1 --topics "Linear equations" "Slope-intercept form"
python main.py list-lessons --class-id 1

# Quiz generation
python main.py generate --count 10 --class-id 1

# Cost tracking
python main.py cost-summary
```

## Troubleshooting

### Database Locked Error

**Symptom:**
```
sqlite3.OperationalError: database is locked
```

**Solution:**
1. Close any applications accessing the database (including DB browsers)
2. Stop the Flask web server (Ctrl+C)
3. Run the reset script again

### Import Errors

**Symptom:**
```
ModuleNotFoundError: No module named 'flask'
```

**Solution:**
```bash
pip install -r requirements.txt
```

If still failing, verify Python version:
```bash
python --version  # Should be 3.9 or higher
```

### Reset Script Won't Run (Windows)

**Symptom:**
```
'bash' is not recognized as an internal or external command
```

**Solution:**
- Use Git Bash (comes with Git for Windows)
- Or use WSL (Windows Subsystem for Linux)
- Or run manual reset steps (see "Manual Reset" section above)

### Demo Data Script Fails

**Symptom:**
```
Error: Active class not set
```

**Solution:**
This is expected if `config.yaml` is missing `active_class_id`. The setup script should create it. If not:

```bash
# Manually set active class
python main.py set-class 1
```

### Web App Won't Start

**Symptom:**
```
Address already in use
```

**Solution:**
Another process is using port 5000. Kill it or use a different port:

```bash
# Find process on Windows
netstat -ano | findstr :5000

# Kill process (replace PID)
taskkill /PID <process_id> /F

# Or use a different port
python app.py --port 5001
```

## Demo Statistics

Use these stats when presenting:

### Development Metrics
- **Test Coverage**: 291 tests passing
  - 160 backend tests (agents, classroom, lessons, cost tracking, database)
  - 131 web/integration tests (routes, forms, auth)
- **Commits**: 51+ commits over 2 weeks
- **Development Cost**: $0 (using MockLLMProvider)
- **Lines of Code**: ~6,500 (Python, HTML, CSS, JS)

### Feature Completeness
- **CLI Commands**: 8 (new-class, list-classes, set-class, log-lesson, list-lessons, generate, cost-summary, ingest)
- **Web Routes**: 30+ (dashboard, classes, lessons, quizzes, analytics)
- **Database Tables**: 10 (classes, lesson_logs, lessons, assets, quizzes, questions, feedback_logs, cost_logs, rate_limits, performance_data)
- **Agent Pipeline**: 3 agents (Generator, Critic, Orchestrator)

### Cost Control
- **Mock Mode**: Zero-cost development with fabricated responses
- **Rate Limiting**: 10 requests/minute (configurable)
- **Cost Tracking**: Per-request logging with provider, model, tokens, cost
- **Approval Gate**: User must confirm before real API calls

## Related Demo Files

- **demo_data/demo_script.md**: Step-by-step walkthrough for presentations
- **demo_data/workshop_slides.md**: Talking points for workshop sessions
- **demo_data/setup_demo.py**: Python script that loads demo data
- **docs/ARCHITECTURE.md**: System architecture diagram and explanation
- **docs/COST_STRATEGY.md**: Cost control strategy and implementation

## Windows-Specific Notes

### Command Syntax
- Use `python` instead of `python3` (Python launcher handles versioning)
- Use `pip` instead of `pip3`
- Use `\` for paths (or `/` in Git Bash)

### Running Bash Scripts
- Install Git for Windows (includes Git Bash)
- Right-click in folder → "Git Bash Here"
- Run: `bash reset_demo.sh`

### Path Separators
- PowerShell: Use backslash `\` or escape forward slash
- Git Bash: Use forward slash `/` (Unix-style)
- Python: Use forward slash `/` or raw strings `r"C:\path\file.db"`

### Emoji/Unicode
- Windows console doesn't render all Unicode well
- Scripts use `[OK]`, `[PASS]`, `[FAIL]` instead of emoji
- Some test output may show `?` for unsupported characters

## Next Steps

After completing the demo setup:

1. **Follow the Demo Script**: See `demo_data/demo_script.md` for guided tour
2. **Read the Architecture**: See `docs/ARCHITECTURE.md` for system design
3. **Review Cost Strategy**: See `docs/COST_STRATEGY.md` for cost control approach
4. **Run the Tests**: `python -m pytest` to verify everything works
5. **Customize Demo Data**: Edit `demo_data/setup_demo.py` to match your needs

## Questions?

- **Project Documentation**: See `README.md` and `CLAUDE.md`
- **OpenSpec Workflow**: See `openspec/` directory for spec-driven development
- **Workshop Materials**: See `demo_data/workshop_slides.md`
- **Architecture Details**: See `docs/ARCHITECTURE.md`

---

**Ready to present?** Run `bash reset_demo.sh`, start the web app, and follow `demo_script.md`. Good luck!
