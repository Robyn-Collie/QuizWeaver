# QuizWeaver User Guide for Teachers

This guide walks you through using QuizWeaver to manage your classes, track lessons, and generate quizzes. QuizWeaver works entirely on your local computer -- no cloud account required for basic use.

---

## Getting Started

### Step 1: Install

```bash
pip install -r requirements.txt
```

### Step 2: Initialize the Database

```bash
python -c "from src.migrations import init_database_with_migrations; init_database_with_migrations('quiz_warehouse.db')"
```

This creates a local SQLite database file. Your data stays on your machine.

### Step 3: Choose Your Interface

QuizWeaver offers two ways to work:

- **Command Line (CLI)** -- Fast, scriptable, great for power users
- **Web Dashboard** -- Visual interface in your browser

---

## Managing Classes

A "class" in QuizWeaver represents a class period or block (e.g., "7th Grade Science - Block A"). Each class tracks its own lessons, knowledge, and quizzes independently.

### Create a Class

**CLI:**
```bash
python main.py new-class --name "7th Grade Science - Block A" --grade "7th Grade" --subject "Science"
```

**Web:** Navigate to `/classes/new` and fill in the form.

### View Your Classes

**CLI:**
```bash
python main.py list-classes
```

This shows a table with each class's name, grade, subject, lesson count, and quiz count. The active class is marked with `*`.

**Web:** Visit `/classes` to see all your classes with stats.

### Set the Active Class

The active class is used as the default for commands like `generate` and `log-lesson`:

```bash
python main.py set-class 2
```

After this, commands will target class ID 2 unless you use the `--class` flag.

### View Class Details

**Web:** Click on any class at `/classes/<id>` to see:
- Assumed knowledge depth for each topic
- Recent lesson history
- Generated quizzes

---

## Logging Lessons

Every time you teach a lesson, log it so QuizWeaver can track what your students know. This information is used to generate better, more targeted quizzes.

### Log a Lesson

**CLI:**
```bash
# Quick log with text
python main.py log-lesson --text "Today we covered photosynthesis and the Calvin cycle"

# Log from a file (e.g., your lesson plan)
python main.py log-lesson --file todays_lesson.txt

# Add teacher notes
python main.py log-lesson --text "Cell division review" --notes "Students struggled with metaphase vs anaphase"

# Override topic detection
python main.py log-lesson --text "Quick review" --topics "mitosis,meiosis"

# Log to a specific class (not the active one)
python main.py log-lesson --class 3 --text "Introduction to genetics and heredity"
```

**Web:** Navigate to `/classes/<id>/lessons/new` and fill in the content, optional topics, and notes.

### How Topic Detection Works

QuizWeaver automatically detects science topics in your lesson text. It recognizes ~40 common topics including: photosynthesis, cell division, mitosis, genetics, evolution, ecosystems, atomic structure, chemical reactions, forces, energy, waves, electricity, plate tectonics, weather, DNA, and more.

You can always override the auto-detected topics using the `--topics` flag.

### Knowledge Depth Tracking

Each time a topic is mentioned in a lesson, QuizWeaver tracks how deeply your class has covered it:

| Depth | Level | Meaning |
|-------|-------|---------|
| 1 | Introduced | Topic mentioned once |
| 2 | Reinforced | Topic revisited in a later lesson |
| 3 | Practiced | Hands-on work or lab activity |
| 4 | Mastered | Pre-test review level |
| 5 | Expert | Advanced applications (maximum) |

This information helps QuizWeaver generate questions at the right difficulty level.

### View Lesson History

**CLI:**
```bash
# All lessons for the active class
python main.py list-lessons

# Last 7 days
python main.py list-lessons --last 7

# Filter by topic
python main.py list-lessons --topic "photosynthesis"

# Date range
python main.py list-lessons --from 2026-01-15 --to 2026-01-31
```

**Web:** Visit `/classes/<id>/lessons` to see the full lesson history with topics and notes.

---

## Generating Quizzes

### Basic Quiz Generation

```bash
python main.py generate
```

This uses the active class context (recent lessons, assumed knowledge) to generate questions. By default, it uses the MockLLMProvider (zero cost) which produces sample questions for testing.

### Customizing Generation

```bash
# Set the number of questions
python main.py generate --count 15

# Set grade level (overrides class setting)
python main.py generate --grade "8th Grade"

# Target specific standards
python main.py generate --sol "SOL 7.1" "SOL 7.3"

# Generate for a specific class
python main.py generate --class 2

# Skip the interactive review step
python main.py generate --no-interactive
```

### How It Works

1. QuizWeaver loads your class's recent lessons and assumed knowledge
2. The **Generator Agent** creates questions aligned with your teaching history
3. The **Critic Agent** reviews the questions for quality and grade-level appropriateness
4. If the critic finds issues, the generator revises (up to 3 attempts)
5. You review the questions interactively (unless `--no-interactive`)
6. Approved questions are saved as PDF and QTI (Canvas import) files

### Output Files

Generated quizzes appear in the `Quiz_Output/` directory as:
- **PDF** -- Printable preview of the quiz
- **QTI ZIP** -- Canvas-compatible import package

### Viewing Quizzes

**Web:** Visit `/quizzes` to see all generated quizzes, or `/quizzes/<id>` for question details.

---

## Using the Web Dashboard

### Starting the Server

```bash
python -c "from src.web.app import create_app; create_app().run(debug=True)"
```

Open http://localhost:5000 in your browser.

### Dashboard Overview

The dashboard at `/dashboard` shows:
- Total number of classes, lessons, and quizzes
- Class names with quick links
- Current LLM provider status (mock = zero cost)

### Navigation

The web interface provides pages for:
- **Classes** -- Create, view, and manage your classes
- **Lessons** -- View lesson history and log new lessons
- **Quizzes** -- Browse generated quizzes and view questions
- **Costs** -- Monitor API usage (relevant only with real providers)

---

## Cost Control

QuizWeaver is designed to be cost-free during normal development and testing.

### Mock Mode (Default)

The default configuration uses `MockLLMProvider`, which:
- Makes zero API calls
- Incurs zero cost
- Returns realistic sample responses
- Is perfect for testing and development

### Using Real AI Providers

When you're ready to generate real quizzes:

1. Set up your API credentials (see README.md)
2. Change `llm.provider` in `config.yaml` to `"gemini"` or `"vertex"`
3. QuizWeaver will prompt you for confirmation before making real API calls
4. Monitor costs with `python main.py cost-summary`

### Cost Estimates

A typical quiz generation session (5 quizzes) costs approximately **$0.025** with Gemini 2.5 Flash.

See [COST_STRATEGY.md](COST_STRATEGY.md) for detailed pricing.

---

## Common Workflows

### Start of Semester Setup

```bash
# Create your class blocks
python main.py new-class --name "Period 1 - Life Science" --grade "7th Grade" --subject "Science"
python main.py new-class --name "Period 3 - Life Science" --grade "7th Grade" --subject "Science"
python main.py new-class --name "Period 5 - Earth Science" --grade "8th Grade" --subject "Science"

# Set your primary class as active
python main.py set-class 1
```

### Daily Lesson Logging

```bash
# After teaching, log what you covered
python main.py log-lesson --text "Covered the stages of mitosis: prophase, metaphase, anaphase, telophase. Lab activity with microscopes."
```

### Assessment Preparation

```bash
# Generate a quiz based on what you've taught
python main.py generate --count 20 --sol "SOL 7.3" "SOL 7.4"
```

### Multi-Class Management

```bash
# Log the same lesson to different classes (if taught differently)
python main.py log-lesson --class 1 --text "Full photosynthesis lesson with Calvin cycle"
python main.py log-lesson --class 2 --text "Introduction to photosynthesis only - light reactions"

# Generate class-specific quizzes
python main.py generate --class 1 --count 15
python main.py generate --class 2 --count 10
```

---

## Troubleshooting

### "No classes found"
Run `python main.py new-class --name "My Class"` to create your first class.

### "Class with ID X not found"
Use `python main.py list-classes` to see available class IDs.

### Quiz generation returns no questions
Ensure `config.yaml` has `llm.provider: "mock"` (or a valid real provider configured). Check that the active class exists.

### Database errors
Re-run migrations: `python -c "from src.migrations import init_database_with_migrations; init_database_with_migrations('quiz_warehouse.db')"`

### Windows file locking
If you see "database is locked" errors, close any other programs accessing the database file and try again.
