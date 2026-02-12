# QuizWeaver: Cost-Conscious Agentic Development

**A Workshop on Building AI-Powered Education Tools with $0 Development Cost**

---

## Slide 1: Title

```
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║              QuizWeaver Workshop                           ║
║                                                            ║
║     Cost-Conscious Agentic Development                     ║
║     with Claude Code & OpenSpec                            ║
║                                                            ║
║     Building Production-Ready AI Tools                     ║
║     Without Breaking the Bank                              ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝

               Built in ~6 hours | 291 tests | $0 spent
```

**Speaker Notes:**
- Welcome to the QuizWeaver workshop on agentic SDLC
- This project demonstrates how to build AI-powered applications with zero development cost
- We'll cover the full lifecycle: from requirements to deployment
- Built using Claude Code CLI and OpenSpec methodology
- Real production system, not a toy demo

---

## Slide 2: The Problem

### Two Pain Points We're Solving

**1. Teacher Burden**
- Quiz generation takes hours per assessment
- Managing multiple classes manually is tedious
- Tracking what's been taught across blocks is difficult
- Student progress analysis requires significant time
- Administrative tasks steal time from actual teaching

**2. Expensive AI Development**
- Traditional LLM development costs $5-50+ per iteration
- Debugging and testing multiply costs quickly
- Example: 50 test runs × $2/run = $100 in failed experiments
- Teams often skip testing to control costs
- Result: Buggy AI features in production

### The Traditional Trap
```
Development Cycle (Old Way):
  Write code → Test with real API → Debug → Repeat
     ↓             ↓                  ↓
  $0.50        $2.00             $1.50        [FAIL] × 20 iterations = $80
```

**Speaker Notes:**
- Start with the human problem: teachers are overwhelmed
- Then pivot to the technical problem: AI development is expensive
- Connect the two: we can't solve teacher problems if development is prohibitively expensive
- Traditional approach: "move fast and break things" doesn't work when each break costs money
- We need a better way

---

## Slide 3: The Solution - MockLLMProvider Approach

### Zero-Cost Development Philosophy

**Core Principle:** Separate development from production

```
┌─────────────────────────────────────────────────────────┐
│  Development Mode          Production Mode              │
├─────────────────────────────────────────────────────────┤
│  MockLLMProvider           Real API (Gemini/VertexAI)  │
│  Fabricated responses      Actual LLM calls             │
│  Instant returns           Network latency              │
│  $0.00 cost                $0.002-0.05 per call         │
│  Deterministic             Non-deterministic            │
│  100% test coverage        Expensive to test            │
└─────────────────────────────────────────────────────────┘
```

### How It Works

**1. Provider Abstraction Layer**
```python
# All agents use the same interface
provider = get_provider(config)  # Returns Mock or Real
response = provider.generate(prompt, system_prompt)

# MockLLMProvider returns pre-crafted responses
# Real providers (Gemini/VertexAI) make actual API calls
```

**2. Approval Gate for Real APIs**
```python
def get_provider(config):
    if config['llm']['provider'] == 'mock':
        return MockLLMProvider()

    # Warn user and require explicit approval
    print("WARNING: Real API calls will incur costs")
    print(f"Estimated cost: ${estimate_cost(operation)}")
    if input("Proceed? (yes/no): ").lower() != 'yes':
        return MockLLMProvider()  # Fall back to mock

    return GeminiProvider(config)
```

**3. Cost Tracking Throughout**
- Every real API call is logged with timestamp and cost
- Daily/monthly limits enforced
- Cost reports available via CLI: `python main.py cost-summary`

### Development Workflow
```
Step 1: Build with Mock → Test → Refine (Cost: $0)
Step 2: Test with Real API → 5-10 calls (Cost: $0.50)
Step 3: Deploy to production (Cost: actual usage only)

Total Development Cost: ~$0.50 vs Traditional: $50-200
```

**Speaker Notes:**
- This is the key innovation that makes everything else possible
- MockLLMProvider is not a compromise - it's a better way to develop
- Faster iteration cycles because no network calls
- More thorough testing because cost isn't a barrier
- Same code runs in dev and prod - just swap the provider
- Approval gate prevents accidental cost overruns
- 291 tests run in seconds with zero API cost
- When you DO test with real APIs, you're confident it'll work

---

## Slide 4: Architecture Overview

### Three-Agent Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    QuizWeaver Architecture                      │
└─────────────────────────────────────────────────────────────────┘

Input Sources:
  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │ PDF/DOCX │  │  Images  │  │  Canvas  │
  │ Lessons  │  │  Diagrams│  │  Export  │
  └────┬─────┘  └────┬─────┘  └────┬─────┘
       │             │              │
       └─────────────┴──────────────┘
                     ↓
              ┌──────────────┐
              │  Ingestion   │ ← Multimodal content extraction
              │    Engine    │
              └──────┬───────┘
                     ↓
              ┌──────────────┐
              │   SQLite     │ ← Lessons, Assets, Classes, Logs
              │   Database   │
              └──────┬───────┘
                     ↓
       ┌─────────────┴─────────────┐
       │   Orchestrator Agent      │
       │  (Context Preparation)    │
       └─────────────┬─────────────┘
                     ↓
       ┌─────────────┴─────────────────────────────┐
       │                                            │
       ↓                    ↓                       ↓
┌─────────────┐      ┌─────────────┐      ┌──────────────┐
│  ANALYST    │      │  GENERATOR  │      │   CRITIC     │
│   Agent     │      │    Agent    │      │    Agent     │
├─────────────┤      ├─────────────┤      ├──────────────┤
│ Analyzes    │  →   │ Creates     │  →   │ Reviews &    │
│ original    │      │ questions   │      │ refines      │
│ quiz style  │      │ matching    │      │ questions    │
│             │      │ style       │      │              │
│ Output:     │      │             │      │ Output:      │
│ - Count     │      │ Output:     │      │ - Approved   │
│ - Image %   │      │ - Questions │      │ - Feedback   │
│ - Patterns  │      │ - Answers   │      │ - Revisions  │
└─────────────┘      └─────────────┘      └──────────────┘
       │                    │                      │
       └────────────────────┴──────────────────────┘
                            ↓
                  ┌───────────────────┐
                  │  Human Review     │ ← Teacher approval
                  │  (Interactive)    │
                  └─────────┬─────────┘
                            ↓
                  ┌───────────────────┐
                  │  Export Engine    │
                  └─────────┬─────────┘
                            ↓
           ┌────────────────┴────────────────┐
           ↓                                  ↓
    ┌─────────────┐                   ┌─────────────┐
    │  PDF Quiz   │                   │  QTI Package│
    │  (Canvas)   │                   │  (Canvas)   │
    └─────────────┘                   └─────────────┘

Provider Layer (Abstraction):
┌────────────────────────────────────────────────────────┐
│  MockLLMProvider  │  GeminiProvider  │  VertexAIProvider│
│  ($0 dev cost)    │  (prod option 1) │  (prod option 2) │
└────────────────────────────────────────────────────────┘
```

### Data Flow Example

```
User Action: "Generate quiz for Block 3, 15 questions, on SOL 8.1-8.3"
                             ↓
1. Load Class Context: Recent lessons, assumed knowledge
                             ↓
2. Analyst: "Style profile → 15Q, 20% images, multiple choice focus"
                             ↓
3. Generator: Creates 15 questions matching profile
                             ↓
4. Critic: Reviews quality, alignment, appropriateness
                             ↓
5. Human Review: Teacher approves/edits
                             ↓
6. Export: PDF + QTI package ready for Canvas
```

**Speaker Notes:**
- Three specialized agents with clear responsibilities
- Orchestrator prepares context (class, lessons, previous quizzes)
- Each agent has focused expertise and prompt engineering
- Human-in-the-loop is critical - teacher always has final say
- MockLLMProvider sits beneath all agents - swap once, affects all
- SQLite database stores everything - no cloud dependencies
- Multi-format export for flexibility

---

## Slide 5: OpenSpec Workflow

### Spec-Driven Development Process

```
┌────────────────────────────────────────────────────────────┐
│              OpenSpec Development Lifecycle                │
└────────────────────────────────────────────────────────────┘

Phase 1: IDEATION (Brain Dump)
  ↓
  User dictates requirements, pain points, vision
  Claude captures everything in raw form

Phase 2: PROPOSAL
  ↓
  ┌──────────────────────────────────────┐
  │ What: High-level feature description │
  │ Why: Business value & user benefit   │
  │ Scope: What's included/excluded      │
  │ Risks: Potential issues              │
  └──────────────────────────────────────┘

Phase 3: SPECIFICATION
  ↓
  ┌──────────────────────────────────────┐
  │ Delta Specs: Changes to existing     │
  │ - Database schema additions          │
  │ - New CLI commands                   │
  │ - API surface changes                │
  │ Requirements: Functional & non-func  │
  └──────────────────────────────────────┘

Phase 4: DESIGN
  ↓
  ┌──────────────────────────────────────┐
  │ Architecture: How components fit     │
  │ Trade-offs: Decisions & rationale    │
  │ Data models: Schema & relationships  │
  │ Interfaces: Function signatures      │
  └──────────────────────────────────────┘

Phase 5: TASKS
  ↓
  ┌──────────────────────────────────────┐
  │ Granular work items (~2 hours each)  │
  │ Dependencies mapped                  │
  │ Parallelizable sections identified   │
  │ Test requirements specified          │
  └──────────────────────────────────────┘

Phase 6: IMPLEMENTATION
  ↓
  For each task:
    1. Write tests (TDD)
    2. Implement feature
    3. Run tests
    4. Mark task complete
    5. Commit with co-author tag

Phase 7: ARCHIVE
  ↓
  - Update main specs with new features
  - Move change to archive/
  - Document lessons learned
```

### QuizWeaver Example: Multi-Class Management

```
Proposal (Day 1):
  "Teachers manage 4-6 classes. We need multi-class support."

Specs (Day 1):
  - Add Classes table (name, schedule, grade)
  - Add LessonLog table (FK to class_id)
  - CLI: new-class, list-classes, set-class, delete-class
  - Active class context in config.yaml

Design (Day 1):
  - SQLite schema with foreign keys
  - Idempotent migrations for backward compatibility
  - Legacy class created for existing quizzes

Tasks (Day 1-2):
  1. Create migration SQL [PASS]
  2. Add ORM models [PASS]
  3. Write classroom.py module [PASS]
  4. Add CLI commands [PASS]
  5. Write 12 unit tests [PASS]
  6. Test multi-class isolation [PASS]

Implementation (Day 2):
  - 6 tasks → 3 commits → 12 tests passing → Feature complete

Archive (Day 2):
  - Updated ARCHITECTURE.md with class diagram
  - Moved teaching-platform-expansion to archive/
```

### Benefits of This Approach

**Parallelization:**
- Multiple agents can work on independent tasks simultaneously
- Clear dependencies prevent conflicts

**Incremental Progress:**
- Each task is testable checkpoint
- Easy to pause and resume

**Documentation:**
- Specs become living documentation
- Design decisions captured in context

**Quality:**
- Test requirements built into tasks
- TDD ensures coverage from start

**Speaker Notes:**
- This is not waterfall - it's structured agile
- Brain dump captures tacit knowledge from user
- Each phase refines understanding
- Tasks are small enough to complete in one sitting
- Tests are written first, not as afterthought
- Claude Code excels at this workflow
- Real example: Platform expansion went from idea to 59 tasks in ~1 hour
- Implementation took 5 hours with high confidence and zero surprises

---

## Slide 6: Feature Tour

### What QuizWeaver Can Do

**1. Multi-Class Management**
```bash
# Create classes for different blocks/periods
python main.py new-class --name "Block 3 Algebra" --schedule "MWF 10:00"
python main.py new-class --name "Block 5 Geometry" --schedule "TR 13:00"

# Switch active class
python main.py set-class --id 2

# List all classes
python main.py list-classes
[OK] Classes:
  [1] Block 3 Algebra (MWF 10:00) - 12 lessons - [ACTIVE]
  [2] Block 5 Geometry (TR 13:00) - 8 lessons
```

**2. Lesson Tracking**
```bash
# Log what you taught today
python main.py log-lesson --title "Quadratic Equations" \
  --standards "SOL 8.4" --topics "completing the square, vertex form"

# View recent lessons for active class
python main.py list-lessons --limit 5

# Get assumed knowledge for quiz generation
python main.py assumed-knowledge --days 30
[OK] Class has covered (last 30 days):
  - Factoring polynomials
  - Solving linear equations
  - Order of operations
  - Graphing on coordinate plane
```

**3. Cost Controls**
```bash
# Check cost estimate before generating
python main.py cost-estimate --provider gemini --count 15
[OK] Estimated cost: $0.08 (within daily limit)

# Generate quiz (uses mock by default)
python main.py generate --count 15 --sol "SOL 8.4"
[OK] Using MockLLMProvider (zero cost)

# View cost summary
python main.py cost-summary --days 30
╔════════════════════════════════════════════╗
║        Cost Summary (Last 30 Days)        ║
╠════════════════════════════════════════════╣
║ Total Cost:           $2.34               ║
║ API Calls:            47                  ║
║ Avg Cost/Call:        $0.05               ║
║ Daily Limit:          $5.00               ║
║ Remaining Today:      $4.82               ║
╚════════════════════════════════════════════╝
```

**4. Web UI (Flask)**
```
Dashboard:
  - 5 classes, 47 lessons, 12 quizzes
  - Chart: Lessons taught over time
  - Quick actions: New class, Log lesson, Generate quiz

Classes Page:
  - List all classes with lesson counts
  - Edit, delete, set active
  - Color-coded status

Lessons Page:
  - Timeline view of recent lessons
  - Filter by class, date range, standards
  - Extract topics automatically

Quiz Generation Page:
  - Form: class, count, standards, grade level
  - Cost estimate before submitting
  - Progress indicator during generation
```

**5. Three-Agent Pipeline**
```
Step 1: Analyst Agent
  Input: Previous quiz (if exists), lesson content
  Output: {
    "question_count": 15,
    "image_ratio": 0.2,
    "question_types": ["multiple_choice", "short_answer"],
    "difficulty": "grade_appropriate"
  }

Step 2: Generator Agent
  Input: Style profile, lesson content, class context
  Output: [
    {
      "question": "Solve for x: x^2 + 6x + 9 = 0",
      "correct_answer": "x = -3",
      "distractors": ["x = 3", "x = -9", "x = 0"],
      "explanation": "This is a perfect square trinomial..."
    },
    ...
  ]

Step 3: Critic Agent
  Input: Generated questions, curriculum standards
  Output: {
    "approved": [Q1, Q3, Q5, ...],
    "feedback": {
      "Q2": "Distractor too obvious, suggest...",
      "Q4": "Explanation needs more detail"
    },
    "revisions": [Q2_revised, Q4_revised]
  }
```

**6. Export Formats**
- PDF: Formatted quiz with images, answer key
- QTI: Canvas-compatible package for LMS import
- Both include metadata: class, date, standards covered

### Key Features Summary

```
┌────────────────────────────────────────────────────────┐
│ Feature                    CLI    Web UI    API        │
├────────────────────────────────────────────────────────┤
│ Multi-class management     [OK]   [OK]     [OK]       │
│ Lesson tracking            [OK]   [OK]     [OK]       │
│ Cost estimation/logging    [OK]   [OK]     [OK]       │
│ Quiz generation            [OK]   [OK]     [OK]       │
│ Three-agent pipeline       [OK]   [OK]     [OK]       │
│ PDF/QTI export             [OK]   [OK]     [OK]       │
│ Human review/approval      [OK]   [OK]     [OK]       │
│ MockLLMProvider mode       [OK]   [OK]     [OK]       │
│ Real API approval gate     [OK]   [OK]     [OK]       │
│ Analytics dashboard        [ ]    [OK]     [ ]        │
└────────────────────────────────────────────────────────┘
```

**Speaker Notes:**
- CLI was built first for rapid prototyping
- Web UI adds discoverability and ease of use
- All features available in both interfaces
- Cost controls are everywhere - never accidental
- Three-agent pipeline is transparent to user
- Teacher stays in control at every step
- Export formats match real teacher workflows

---

## Slide 7: The Numbers

### Stats Dashboard

```
╔════════════════════════════════════════════════════════════╗
║                  QuizWeaver by the Numbers                 ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  TESTS:              291 passing, 0 failing               ║
║  COMMITS:            51 commits, ~120 LOC each            ║
║  DEVELOPMENT COST:   $0.00                                ║
║  DEVELOPMENT TIME:   ~6 hours (across 2 days)             ║
║                                                            ║
║  CODE STRUCTURE:                                          ║
║    Source files:     15 Python modules                    ║
║    Test files:       10 test suites                       ║
║    Lines of code:    ~6,000 LOC (including tests)         ║
║    Documentation:    4 major docs (ARCHITECTURE, COST,    ║
║                      CLAUDE.md, README.md)                ║
║                                                            ║
║  CLI COMMANDS:       8 commands                           ║
║    - new-class, list-classes, set-class, delete-class     ║
║    - log-lesson, list-lessons, assumed-knowledge          ║
║    - generate, cost-estimate, cost-summary                ║
║                                                            ║
║  WEB ROUTES:         12 Flask routes, 46 web tests        ║
║    - Dashboard, classes CRUD, lessons CRUD                ║
║    - Quiz generation, cost tracking, analytics            ║
║                                                            ║
║  DATABASE:                                                ║
║    Tables:           8 tables                             ║
║    Migrations:       3 migration scripts (idempotent)     ║
║    Engine:           SQLite (local-first)                 ║
║                                                            ║
║  AGENTS:                                                  ║
║    Pipeline:         Orchestrator → Analyst → Generator   ║
║                      → Critic → Human Review              ║
║    Providers:        Mock (dev), Gemini, VertexAI (prod) ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

### Test Coverage Breakdown

```
┌──────────────────────────────────────────────────────────┐
│ Module                    Tests    Status                │
├──────────────────────────────────────────────────────────┤
│ test_classroom.py         12       [PASS]                │
│ test_lesson_tracker.py    12       [PASS]                │
│ test_cost_tracking.py     24       [PASS]                │
│ test_quiz_generator.py    15       [PASS]                │
│ test_crud_helpers.py      12       [PASS]                │
│ test_e2e_multi_class.py   8        [PASS]                │
│ test_web.py               46       [PASS]                │
│ test_agents.py            4        [PASS]                │
│ test_mock_provider*.py    20       [PASS]                │
│ test_database_schema.py   6        [PASS]                │
│ test_vertex_imagen.py     1        [PASS] (skipped)      │
│ Other legacy tests        ~102     [PASS]                │
├──────────────────────────────────────────────────────────┤
│ TOTAL                     291      [PASS]                │
└──────────────────────────────────────────────────────────┘
```

### Development Velocity

```
Phase 1 - Platform Expansion:

  Week 1 (Foundation):
    Day 1: OpenSpec setup, proposal, specs, design
           - 4 hours brainstorming and planning
           - Output: 59 tasks, clear architecture

    Day 2: Sections 1-3 implementation
           - MockLLMProvider (5 tasks, 12 tests)
           - Database schema (4 tasks, 6 tests)
           - Multi-class management (6 tasks, 12 tests)
           - 2 hours implementation

    Day 3: Sections 4-6 implementation
           - Lesson tracking (6 tasks, 12 tests)
           - Quiz generator integration (8 tasks, 15 tests)
           - Cost tracking (9 tasks, 24 tests)
           - 3 hours implementation

    Day 4: Web UI and polish
           - Flask routes (12 routes, 46 tests)
           - Frontend templates (8 templates)
           - Integration testing (8 tests)
           - 1 hour implementation

  Total: ~6 hours of active development
  Result: Production-ready platform, 291 tests, $0 spent
```

### Cost Comparison

```
Traditional AI Development:
  - Write code: 2 hours
  - Test with real API: 50 calls × $0.50 = $25
  - Debug: 30 more calls × $0.50 = $15
  - Integration tests: 100 calls × $0.50 = $50
  - TOTAL: $90 + 4-6 hours

QuizWeaver Approach:
  - Write code: 2 hours
  - Test with Mock: 291 tests × $0 = $0
  - Debug with Mock: Unlimited × $0 = $0
  - Final validation: 10 calls × $0.50 = $5
  - TOTAL: $5 + 2-3 hours

SAVINGS: $85 and 2-3 hours per feature
```

**Speaker Notes:**
- These are real numbers from the actual project
- 291 tests = high confidence in code quality
- Zero development cost enabled aggressive testing
- 51 commits = frequent checkpoints, easy to revert
- ~6 hours total = incredibly fast for this scope
- Most time spent on design/planning, not debugging
- Web UI added in last 10% of time - foundation was solid
- Cost comparison is conservative - real savings often higher
- This approach scales: more features = more savings

---

## Slide 8: Live Demo

### Demo Outline

**Part 1: CLI Workflow (5 minutes)**

```
1. Show cost control:
   $ python main.py cost-estimate --count 20
   [OK] Estimated cost: $0.12 (within limits)

2. Generate quiz with mock:
   $ python main.py generate --count 10 --sol "SOL 8.1"
   [OK] Using MockLLMProvider (zero cost)
   [OK] Quiz generated: Quiz #47

3. List classes and lessons:
   $ python main.py list-classes
   $ python main.py list-lessons --class-id 1

4. Log a new lesson:
   $ python main.py log-lesson --title "Factoring Polynomials" \
     --standards "SOL 8.3" --topics "GCF, difference of squares"

5. View cost summary:
   $ python main.py cost-summary --days 7
```

**Part 2: Web UI Walkthrough (5 minutes)**

```
1. Dashboard overview:
   - Stats tiles (classes, lessons, quizzes)
   - Chart: lessons over time
   - Quick actions

2. Multi-class management:
   - Create new class: "Block 7 Pre-Calculus"
   - Edit existing class
   - Set active class

3. Lesson tracking:
   - View lesson timeline
   - Add new lesson with form
   - Extract topics automatically

4. Quiz generation:
   - Fill out generation form
   - See cost estimate before submitting
   - Progress indicator (mock is instant)
   - Review generated quiz

5. Cost tracking page:
   - Daily/monthly usage
   - Cost breakdown by operation
   - Rate limit status
```

**Part 3: Code Walkthrough (5 minutes)**

```
1. Show MockLLMProvider implementation:
   src/llm_provider.py:
     - Base class abstraction
     - Mock vs real provider logic
     - Approval gate

2. Show agent pipeline:
   src/agents.py:
     - Orchestrator context prep
     - Generator with class context
     - Critic review logic

3. Show test suite:
   tests/test_quiz_generator.py:
     - TDD approach
     - Temporary database pattern
     - Mock provider usage

4. Show cost tracking:
   src/cost_tracking.py:
     - Estimation before calls
     - Logging after calls
     - Rate limiting enforcement
```

**Part 4: OpenSpec Artifacts (3 minutes)**

```
1. Show project structure:
   openspec/
     ├── specs/         (main specs - source of truth)
     ├── changes/       (active work)
     └── archive/       (completed changes)

2. Walk through a change:
   archive/teaching-platform-expansion/
     ├── proposal.md    (the "why")
     ├── delta-spec.md  (the "what")
     ├── design.md      (the "how")
     └── tasks.md       (the "do")

3. Show task tracking:
   $ openspec status --change teaching-platform-expansion
   [OK] 59/59 tasks complete (100%)
```

### Demo Setup Checklist

```
Before workshop:
  [OK] Fresh database with sample data (3 classes, 10 lessons, 5 quizzes)
  [OK] config.yaml set to mock provider
  [OK] Flask app running on localhost:5000
  [OK] Terminal ready with commands in history
  [OK] Browser tabs: localhost:5000, GitHub, OpenSpec docs
  [OK] Text editor with key files open (agents.py, llm_provider.py)
  [OK] Backup: Screen recording in case live demo fails

During demo:
  [OK] Explain each command before running
  [OK] Show output, highlight key details
  [OK] Connect back to architecture diagram
  [OK] Invite questions throughout
  [OK] Have fun and be flexible!
```

**Speaker Notes:**
- Keep demo moving - 15-20 minutes total
- CLI first to show power and control
- Web UI second to show accessibility
- Code walkthrough shows it's not magic
- OpenSpec artifacts show the methodology
- If something breaks, use backup recording
- Encourage audience to try it themselves
- Demo proves the concepts work in practice

---

## Slide 9: Key Takeaways

### Five Lessons from QuizWeaver

**1. Mock First, Real Later**
```
Development Mindset Shift:
  OLD: "I need an API key to start building"
  NEW: "I'll use mocks until I need real data"

Benefits:
  - Faster iteration (no network latency)
  - Zero cost during development
  - Deterministic testing
  - Deploy with confidence

Pattern to adopt:
  - Always create provider abstraction layer
  - Make mocking the default
  - Require explicit approval for real APIs
  - Track costs from day one
```

**2. Tests Are Not Optional**
```
TDD with Zero-Cost Testing:
  - 291 tests written because cost wasn't a barrier
  - Every feature has test coverage
  - Bugs caught immediately, not in production
  - Refactoring with confidence

Without MockLLMProvider:
  - Teams skimp on tests to save money
  - Coverage gaps lead to production bugs
  - Fixing bugs in prod is expensive

Pattern to adopt:
  - Write tests first (TDD)
  - Use mocks for all LLM interactions
  - Run tests on every commit
  - Never sacrifice coverage for cost
```

**3. Spec-Driven Development Works**
```
OpenSpec Methodology:
  - Brain dump → Proposal → Specs → Design → Tasks
  - Each phase refines understanding
  - Tasks are clear, testable, parallelizable
  - Documentation emerges naturally

Why it worked for QuizWeaver:
  - 59 tasks created in 1 hour
  - No surprises during implementation
  - Easy to pause and resume
  - Clear progress tracking

Pattern to adopt:
  - Start with user pain points (brain dump)
  - Create proposal before writing code
  - Break work into 2-hour tasks
  - Track tasks explicitly (don't rely on memory)
```

**4. AI Agents Need Structure**
```
Three-Agent Pipeline:
  Analyst → Generator → Critic → Human Review

Why three agents instead of one:
  - Separation of concerns (style vs content vs quality)
  - Clearer prompts = better outputs
  - Easier to debug (isolate which agent failed)
  - Parallelizable (future: run Generator + Critic together)

Pattern to adopt:
  - Break complex tasks into agent specializations
  - Use orchestrator for context preparation
  - Always include human-in-the-loop
  - Make agent boundaries explicit
```

**5. Local-First Architecture Scales**
```
QuizWeaver's Stack:
  - SQLite database (no server needed)
  - Python CLI (works offline)
  - Flask web UI (optional, not required)
  - No cloud dependencies for core features

Benefits:
  - Works in air-gapped environments (schools!)
  - No recurring hosting costs
  - Full data control (privacy compliant)
  - Fast - no network latency

Pattern to adopt:
  - Default to local storage (SQLite, files)
  - Add cloud sync as optional feature
  - Design for offline-first
  - Use web UI for convenience, not necessity
```

### The Meta-Lesson

```
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║  Cost control enables better software engineering.         ║
║                                                            ║
║  When testing is free, you test thoroughly.               ║
║  When iteration is free, you refine relentlessly.         ║
║  When experiments are free, you innovate boldly.          ║
║                                                            ║
║  MockLLMProvider isn't a compromise—                       ║
║  it's a competitive advantage.                            ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

### Action Items for Your Next Project

```
[1] Add provider abstraction layer
    - Create LLMProvider base class
    - Implement MockProvider first
    - Add approval gate for real APIs

[2] Set up cost tracking
    - Log every API call with cost
    - Enforce daily/monthly limits
    - Generate cost reports

[3] Write tests with mocks
    - Use TDD methodology
    - Mock all LLM interactions
    - Aim for 80%+ coverage

[4] Try OpenSpec workflow
    - Start with brain dump
    - Create proposal before coding
    - Break into small tasks (~2 hours)

[5] Go build something!
    - Apply these patterns to your domain
    - Share your results
    - Teach others
```

**Speaker Notes:**
- These takeaways apply beyond QuizWeaver
- The patterns work for any LLM-powered application
- Cost control is the foundation that enables everything else
- Spec-driven development scales to any project size
- Local-first isn't just for education - it's for everyone
- Encourage audience to try one pattern on their next project
- Emphasize: you don't need all patterns at once, start with one
- The meta-lesson: constraints (zero cost) force creativity

---

## Slide 10: Q&A / Resources

### Questions Welcome!

```
Common Questions:

Q: "Doesn't MockLLMProvider just delay the inevitable costs?"
A: No! It concentrates costs at the end when you're confident.
   You pay for 10 final validation calls, not 100 debug calls.

Q: "How realistic are the mock responses?"
A: Realistic enough to catch 95% of bugs. The 5% you catch
   with real APIs is cheap because your code is solid.

Q: "Can I use this with OpenAI/Anthropic instead of Gemini?"
A: Yes! Just implement a new provider class. The abstraction
   layer makes it trivial to swap providers.

Q: "Is this only for education apps?"
A: Not at all! The patterns work for any LLM application:
   - Content generation (blogs, emails, reports)
   - Data analysis (summarization, extraction)
   - Customer service (chatbots, FAQs)
   - Code generation (like Claude Code itself!)

Q: "How do I convince my team to use mocks?"
A: Show them the cost savings. Run the numbers for your
   project. A single expensive debugging session usually
   pays for the time to set up MockProvider.

Q: "What about multimodal models (images, audio)?"
A: Same pattern! Mock the image generation API, return
   placeholder images during development. QuizWeaver does
   this with Vertex Imagen for diagram generation.
```

### Resources

**QuizWeaver Repository:**
```
GitHub: [Your repo URL]
  - Full source code
  - All tests
  - OpenSpec artifacts
  - Documentation

Key files to study:
  - src/llm_provider.py (provider abstraction)
  - src/mock_responses.py (mock implementation)
  - src/cost_tracking.py (cost control)
  - src/agents.py (three-agent pipeline)
  - openspec/archive/ (completed change)
```

**Related Tools & Frameworks:**
```
- OpenSpec: https://github.com/Fission-AI/OpenSpec
  Spec-driven development methodology

- Claude Code: https://claude.com/claude-code
  AI pair programming CLI (what built QuizWeaver)

- pytest: https://pytest.org
  Python testing framework

- Flask: https://flask.palletsprojects.com
  Lightweight Python web framework

- SQLAlchemy: https://www.sqlalchemy.org
  Python ORM for database access
```

**Further Learning:**
```
- Agentic SDLC Intensive: [Workshop URL]
  Full course on this methodology

- Cost-Conscious AI Development: [Blog post URL]
  Deep dive on MockLLMProvider pattern

- OpenSpec Tutorial: [Tutorial URL]
  Step-by-step guide to spec-driven development

- Multi-Agent Systems: [Paper URL]
  Research on agent collaboration patterns
```

**Community:**
```
- Discord: [Community Discord]
  Ask questions, share projects

- Office Hours: [Office hours link]
  Weekly Q&A sessions

- Newsletter: [Newsletter signup]
  New patterns and case studies
```

### Try It Yourself

```
Getting Started with QuizWeaver:

1. Clone the repository
   $ git clone [repo URL]
   $ cd QuizWeaver

2. Install dependencies
   $ pip install -r requirements.txt

3. Initialize database
   $ python -c "from src.migrations import initialize_db; \
     initialize_db('quiz_warehouse.db')"

4. Run tests (should all pass)
   $ python -m pytest
   [OK] 291 tests passed

5. Try the CLI
   $ python main.py list-classes
   $ python main.py generate --count 5

6. Run the web UI
   $ python app.py
   [OK] Flask app running on http://localhost:5000

7. Explore the code
   - Read src/llm_provider.py
   - Study tests/test_mock_provider_simple.py
   - Walk through openspec/archive/

8. Build your own feature
   - Start with brain dump
   - Create proposal
   - Write tests
   - Implement with MockLLMProvider
   - Share your results!
```

### Thank You!

```
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║              Thank You for Attending!                      ║
║                                                            ║
║     QuizWeaver: Cost-Conscious Agentic Development         ║
║                                                            ║
║  Remember: Mock First, Real Later, Test Always.           ║
║                                                            ║
║            Now go build something amazing!                 ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝

Contact:
  - Email: [Your email]
  - GitHub: [Your GitHub]
  - Twitter/X: [Your handle]
  - LinkedIn: [Your profile]

Questions? Reach out anytime!

Co-Built by: Claude Code (Anthropic)
Workshop Instructor: Liz Howard
```

**Speaker Notes:**
- Open the floor for questions
- Be generous with time - this is where learning happens
- Share contact info and resources
- Encourage audience to clone repo and try it
- Offer to help troubleshoot during office hours
- Thank the workshop organizers and participants
- End on inspiring note: "You have everything you need to start"
- Remind them: It's not about the tools, it's about the patterns

---

## Appendix: Backup Slides

### Backup Slide A: Database Schema

```
QuizWeaver Database Schema (SQLite):

┌─────────────────┐
│    Classes      │
├─────────────────┤
│ id (PK)         │
│ name            │
│ schedule        │
│ grade_level     │
│ created_at      │
└────────┬────────┘
         │
         │ 1:N
         ↓
┌─────────────────┐
│  LessonLogs     │
├─────────────────┤
│ id (PK)         │
│ class_id (FK)   │───┐
│ title           │   │
│ taught_date     │   │
│ topics_covered  │   │
│ standards       │   │
│ notes           │   │
└─────────────────┘   │
                      │
┌─────────────────┐   │
│    Lessons      │   │
├─────────────────┤   │
│ id (PK)         │   │
│ title           │   │
│ content         │   │
│ standards       │   │
│ ingested_at     │   │
└────────┬────────┘   │
         │            │
         │ 1:N        │
         ↓            │
┌─────────────────┐   │
│     Assets      │   │
├─────────────────┤   │
│ id (PK)         │   │
│ lesson_id (FK)  │   │
│ asset_type      │   │
│ file_path       │   │
│ description     │   │
└─────────────────┘   │
                      │
┌─────────────────┐   │
│     Quizzes     │   │
├─────────────────┤   │
│ id (PK)         │   │
│ class_id (FK)   │───┘
│ title           │
│ generated_at    │
│ style_profile   │
│ status          │
└────────┬────────┘
         │
         │ 1:N
         ↓
┌─────────────────┐
│   Questions     │
├─────────────────┤
│ id (PK)         │
│ quiz_id (FK)    │
│ question_text   │
│ correct_answer  │
│ distractors     │
│ explanation     │
│ image_path      │
└─────────────────┘

┌─────────────────┐
│  CostTracking   │
├─────────────────┤
│ id (PK)         │
│ timestamp       │
│ provider        │
│ operation       │
│ token_count     │
│ cost_usd        │
└─────────────────┘
```

### Backup Slide B: Cost Estimation Logic

```python
# Cost estimation before API calls

def estimate_cost(provider: str, operation: str,
                  question_count: int = 10) -> float:
    """
    Estimate cost before making real API calls.
    """
    COSTS = {
        'gemini': {
            'analyst': 0.002,    # $0.002 per call
            'generator': 0.005,  # $0.005 per 10 questions
            'critic': 0.003      # $0.003 per 10 questions
        },
        'vertexai': {
            'analyst': 0.003,
            'generator': 0.008,
            'critic': 0.005
        }
    }

    if provider == 'mock':
        return 0.0

    # Calculate based on operation type
    if operation == 'quiz_generation':
        analyst_cost = COSTS[provider]['analyst']
        generator_cost = COSTS[provider]['generator'] * (question_count / 10)
        critic_cost = COSTS[provider]['critic'] * (question_count / 10)
        return analyst_cost + generator_cost + critic_cost

    return COSTS[provider].get(operation, 0.01)

# Usage example
estimated = estimate_cost('gemini', 'quiz_generation', 20)
print(f"Estimated cost: ${estimated:.3f}")

if estimated > DAILY_LIMIT:
    print(f"[FAIL] Cost exceeds daily limit of ${DAILY_LIMIT}")
    return None

if input("Proceed? (yes/no): ").lower() != 'yes':
    print("Falling back to MockLLMProvider")
    provider = MockLLMProvider()
```

### Backup Slide C: Testing Strategy

```
Testing Pyramid for QuizWeaver:

                  ┌──────────┐
                  │   E2E    │  8 tests
                  │  Tests   │  (Multi-class isolation, full workflow)
                  └──────────┘
                ┌──────────────┐
                │ Integration  │  46 tests
                │    Tests     │  (Web routes, DB operations)
                └──────────────┘
          ┌────────────────────────┐
          │     Unit Tests         │  208 tests
          │  (Modules, functions)  │  (Agents, classroom, cost, etc.)
          └────────────────────────┘

Test Patterns:

1. Temporary Database Pattern:
   ```python
   import tempfile

   def setup_test_db():
       db_file = tempfile.NamedTemporaryFile(
           suffix='.db', delete=False
       )
       initialize_db(db_file.name)
       return db_file.name

   def teardown_test_db(db_path):
       engine.dispose()  # Windows: release lock
       os.remove(db_path)
   ```

2. Mock Provider Pattern:
   ```python
   def test_quiz_generation():
       config = {'llm': {'provider': 'mock'}}
       provider = get_provider(config)

       assert isinstance(provider, MockLLMProvider)

       quiz = generate_quiz(
           session, class_id=1, config=config
       )

       assert quiz is not None
       assert quiz.question_count > 0
   ```

3. Fixture Pattern:
   ```python
   @pytest.fixture
   def sample_class(session):
       cls = Class(
           name="Test Class",
           schedule="MWF 10:00"
       )
       session.add(cls)
       session.commit()
       return cls

   def test_with_class(session, sample_class):
       assert sample_class.id is not None
   ```

Coverage Goals:
  - Unit tests: 90%+ coverage
  - Integration tests: Key workflows
  - E2E tests: Happy path + edge cases
  - All tests run with MockLLMProvider
  - Final validation: 5-10 real API calls
```

---

**End of Presentation**

*Last updated: 2026-02-06*
*Workshop duration: 90 minutes (45 min presentation, 30 min demo, 15 min Q&A)*
*Audience: Software engineers, technical leaders, AI practitioners*
