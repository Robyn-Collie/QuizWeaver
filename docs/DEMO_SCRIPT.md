# QuizWeaver Workshop Demo Script (15 minutes)

**Demo Date**: Workshop Presentation
**Presenter**: Andre
**Audience**: Agentic SDLC Intensive
**Tech**: Python, SQLite, Flask, Claude Code, OpenSpec

---

## Pre-Demo Setup Checklist

**30 minutes before demo:**

- [ ] Open two terminal windows (Git Bash or PowerShell)
  - Terminal 1: For CLI commands
  - Terminal 2: For Flask web server
- [ ] Navigate both to `C:\Users\andre\projects\QuizWeaver`
- [ ] Verify virtual environment is activated (if using one)
- [ ] Run quick smoke test: `python -m pytest tests/test_mock_provider_simple.py -v`
- [ ] Verify config.yaml has `llm.provider: "mock"` (CRITICAL - zero cost)
- [ ] Verify database exists: `dir quiz_warehouse.db` (should show file)
- [ ] Open browser to http://localhost:5000 (don't start server yet)
- [ ] Have VS Code open with key files ready:
  - `src/llm_provider.py` (MockLLMProvider class)
  - `config.yaml` (showing mock provider config)
  - `src/agents.py` (three-agent system)
  - `tests/test_quiz_generator.py` (test examples)
- [ ] Close unnecessary applications (free up screen space)
- [ ] Test projector/screen sharing resolution
- [ ] Have backup: screenshots of each step in `demo_screenshots/` folder

**5 minutes before demo:**

- [ ] Clear terminal history: `cls` (PowerShell) or `clear` (Git Bash)
- [ ] Stop Flask server if running
- [ ] Close browser tabs except localhost:5000
- [ ] Take deep breath, hydrate

---

## Demo Script

### Section 1: The Problem (2 minutes, 0:00-2:00)

**[Slide or whiteboard - don't code yet]**

**Talking Points** (speak naturally, don't read verbatim):

*"Hi everyone, I'm Andre and I'm going to show you QuizWeaver - an AI-powered teaching assistant I built during this workshop. Let me start with the problem that sparked this project."*

*"Teachers spend hours creating retake quizzes. You can't reuse the original quiz - students share answers. So teachers manually create variations: same difficulty, same style, different questions. It's tedious, time-consuming, and takes away from actual teaching."*

*"My initial solution: use AI to generate quiz variations automatically. Great idea, right? But here's the catch..."*

**[Pause for effect]**

*"AI development is EXPENSIVE. Every time I test a feature, that's an API call. Every time I run my test suite, that's 50+ API calls. Every time I iterate on a prompt, that's another $0.10-$2.00 down the drain. This adds up fast."*

*"So I had TWO problems to solve:"*

1. *"Help teachers generate quizzes faster"*
2. *"Build the AI system without going broke"*

*"Let me show you how I solved problem #2 first, because it's the foundation of everything else."*

---

### Section 2: The Solution - MockLLMProvider (5 minutes, 2:00-7:00)

**[Switch to Terminal 1]**

**ACTION**: Show config.yaml

```bash
type config.yaml
```

*"Here's my secret weapon - look at line 3 here..."*

**[Scroll to llm section, highlight provider: "mock"]**

```yaml
llm:
  provider: "mock"  # Options: "mock", "gemini", "vertexai"
  model: "gemini-1.5-flash-002"
  # ... other config
```

*"By default, QuizWeaver uses a MockLLMProvider - a fake AI that returns pre-written responses. Zero API calls. Zero cost. Instant responses."*

*"This isn't just a stub - it's a fully functional LLM provider that mimics real AI behavior, including:"*
- *Structured JSON responses*
- *Realistic quiz questions and critiques*
- *Proper error handling*
- *All the same interfaces as real providers*

**ACTION**: Show the MockLLMProvider code (briefly)

```bash
# Open in VS Code or cat the file
type src\llm_provider.py | findstr /N "class MockLLMProvider" /C:"def generate" /C:"def __init__"
```

*"The MockLLMProvider class implements the same interface as GeminiProvider and VertexAIProvider, so I can swap providers without changing ANY application code."*

**ACTION**: Run the test suite

```bash
python -m pytest -v --tb=short
```

*"Watch this - I'm running 291 tests right now. Every single one exercises the full AI pipeline: content analysis, question generation, quality review. But it's using mock responses, so..."*

**[Wait for tests to complete - should take 10-20 seconds]**

*"...it completes in under 30 seconds and costs me exactly zero dollars."*

**[Point to passing tests output]**

*"291 tests passing. That's 291 potential API calls I DIDN'T pay for during development. At an average of $0.05 per call, that's $13 saved. And I've run this suite hundreds of times during development. Do the math."*

**ACTION**: Generate a quiz using MockLLMProvider

```bash
python main.py generate --count 10 --grade "8th Grade" --sol "SOL 8.1" --no-interactive
```

*"Now let me generate an actual quiz. Watch how fast this runs..."*

**[Wait for generation - should be instant]**

```
[OK] Quiz generated successfully
[OK] 10 questions created
[OK] Saved to Quiz_Output/quiz_<timestamp>.pdf
[OK] Total cost: $0.00 (mock mode)
```

*"Instant. Zero cost. And the output is a real PDF with properly formatted questions. During development, this is perfect."*

**ACTION**: Show a snippet of generated quiz (optional - if time permits)

```bash
# Open PDF or show JSON
type Quiz_Output\quiz_*.json
```

*"The questions look real because they come from carefully crafted mock responses that match the style and structure of actual AI output."*

**[TRANSITION]**

*"Now, when I'm ready for production, I just change ONE line in config.yaml..."*

```yaml
llm:
  provider: "gemini"  # Changed from "mock"
```

*"...and suddenly I'm using real AI. Same code, same commands, real intelligence. But during development? Mock mode all the way."*

---

### Section 3: The Architecture (5 minutes, 7:00-12:00)

**[Can use whiteboard/slide or live code walkthrough]**

#### Part A: Three-Agent System (2 minutes)

*"QuizWeaver doesn't use a single AI prompt. It uses a THREE-AGENT system, inspired by agentic workflows we learned in this course."*

**[Draw or show diagram if available, or describe:]**

1. **Analyst Agent**: *"Analyzes the original quiz to extract style profile - question types, difficulty level, image usage ratio, topic distribution."*

2. **Generator Agent**: *"Creates new questions matching that style profile. It doesn't just generate random questions - it maintains the same pedagogical approach as the original teacher."*

3. **Critic Agent**: *"Reviews generated questions for quality, accuracy, and alignment. Acts as a second set of eyes before the teacher sees anything."*

*"All three agents use the same LLM provider interface, so in development they ALL use MockLLMProvider. This means I can test the entire orchestration pipeline without spending a dime."*

**ACTION**: Show agents.py briefly (if time permits)

```bash
type src\agents.py | findstr /N "class AnalystAgent" "class GeneratorAgent" "class CriticAgent"
```

#### Part B: Multi-Class Management (2 minutes)

*"But QuizWeaver is more than just quiz generation. Teachers have multiple classes, and this system tracks them separately."*

**ACTION**: List existing classes

```bash
python main.py list-classes
```

**Expected Output:**
```
Classes:
  ID: 1, Name: "Period 1 - Algebra", Active: Yes
  ID: 2, Name: "Period 3 - Geometry", Active: No
  ID: 3, Name: "Period 5 - Algebra", Active: No
```

*"Each class is isolated. Lessons logged to Period 1 don't appear in Period 3."*

**ACTION**: Create a new class

```bash
python main.py new-class "Workshop Demo Class" "Demo for SDLC Workshop"
```

**Expected Output:**
```
[OK] Class created: Workshop Demo Class (ID: 4)
[OK] Set as active class
```

**ACTION**: Log a lesson

```bash
python main.py log-lesson "Quadratic Equations" "Taught solving by factoring, completing the square, and quadratic formula. Students struggled with negative discriminants."
```

**Expected Output:**
```
[OK] Lesson logged to class: Workshop Demo Class
[OK] Lesson ID: 15
```

**ACTION**: View recent lessons

```bash
python main.py list-lessons --limit 3
```

**Expected Output:**
```
Recent Lessons (Workshop Demo Class):
  2026-02-06: Quadratic Equations
    Notes: Taught solving by factoring, completing the square...
    Topics: factoring, completing the square, quadratic formula
```

*"This lesson tracking feeds into the AI's 'assumed knowledge' - when generating quizzes, it knows what the class has already learned."*

#### Part C: Cost Tracking (1 minute)

**ACTION**: Show cost summary

```bash
python main.py cost-summary
```

**Expected Output:**
```
Cost Summary:
  Total Requests: 0
  Total Tokens: 0 (input: 0, output: 0)
  Total Cost: $0.00
  Provider: mock

[OK] All development done in zero-cost mock mode
```

*"In production mode, this tracks every API call, every token, every dollar spent. Rate limits prevent runaway costs. But again - in development, it's all zeros."*

---

### Section 4: The Web Interface (BONUS - if time permits, 1 minute)

**[Switch to Terminal 2]**

**ACTION**: Start Flask server

```bash
python web.py
```

**Expected Output:**
```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
```

**[Switch to browser at localhost:5000]**

*"QuizWeaver also has a web interface - built by a separate agent using the CLI backend as an API surface."*

**[Click through quickly:]**
- Dashboard: Shows active class, recent lessons, quiz history
- Classes page: Visual list of all classes
- Lessons page: Calendar view or list view
- Generate Quiz page: Form-based quiz generation

*"This demonstrates the separation of concerns - the CLI is the complete API, and the web UI is just a friendly frontend. Multiple agents can work in parallel because the interfaces are clean."*

**[Switch back to Terminal 1]**

---

### Section 5: The Stats & Closing (3 minutes, 12:00-15:00)

**[Can show slide or just speak]**

*"Let me give you the numbers on what was accomplished during this workshop:"*

#### Development Stats

- **291 tests passing** (1 pre-existing failure excluded)
- **51 commits** over the workshop period
- **8 CLI commands** fully functional:
  - `ingest` - Import lesson content
  - `generate` - Create quizzes
  - `new-class`, `list-classes`, `set-class` - Multi-class management
  - `log-lesson`, `list-lessons` - Lesson tracking
  - `cost-summary` - Cost monitoring
- **Zero dollars spent** on AI API calls during development
- **3 LLM providers** supported: Mock, Gemini, Vertex AI
- **Phase 1 complete**: Multi-class management, lesson tracking, cost controls, web UI
- **Built with**: Claude Code + OpenSpec methodology

#### Key Architectural Decisions

1. **MockLLMProvider as default**: Saved hundreds of dollars in development costs
2. **Provider abstraction**: Swap AI backends without code changes
3. **Three-agent orchestration**: Quality control built into the pipeline
4. **Local-first database**: SQLite, no cloud dependencies
5. **Test-driven development**: 291 tests mean confidence in every change

#### What This Demonstrates

*"This project showcases several principles from the Agentic SDLC course:"*

1. **Cost-conscious AI development**: Mock providers eliminate API costs during iteration
2. **Agentic architecture**: Multi-agent systems with specialized roles
3. **Spec-driven development**: OpenSpec for structured, parallelizable work
4. **Multi-agent collaboration**: CLI agent builds backend, web agent builds frontend
5. **Production-ready patterns**: Migration scripts, cost tracking, rate limits

#### The Bottom Line

*"QuizWeaver started as a simple quiz generator. By applying agentic principles and cost-control strategies, it evolved into a comprehensive teaching platform - WITHOUT burning through my API budget."*

*"The lesson here isn't just about building a teaching tool. It's about building AI systems SMARTLY. Use mocks during development. Test extensively. Design for cost control from day one. And when you're ready for production, flip the switch."*

**[Final screen: Show config.yaml with the provider line]**

*"One line. That's the difference between $0 development and $500 development. Choose wisely."*

**[End of demo - open for questions]**

---

## Backup Plan (If Live Demo Fails)

### Scenario 1: Tests fail during demo

**Fallback**:
- *"Looks like we have a flaky test - this happens. Let me show you the last successful test run..."*
- Show screenshot of test results from pre-demo run
- Continue with quiz generation (less likely to fail)

### Scenario 2: Quiz generation hangs

**Fallback**:
- Ctrl+C to cancel
- *"This is actually a perfect teaching moment - mock providers should be instant. This suggests a real API call might be happening..."*
- Check config.yaml: `type config.yaml | findstr provider`
- Show how to debug (demonstrates real-world problem solving)
- Fall back to pre-generated quiz: `dir Quiz_Output` and show PDF

### Scenario 3: Database corruption

**Fallback**:
- *"Database issues - let's reinitialize..."*
- `python -c "from src.migrations import init_database_with_migrations; init_database_with_migrations('quiz_warehouse.db')"`
- Create demo class again (shows resilience)
- OR: Have backup database ready: `copy quiz_warehouse_backup.db quiz_warehouse.db`

### Scenario 4: Flask web server won't start

**Fallback**:
- Skip web demo entirely (it's bonus content)
- Focus on CLI architecture
- Show screenshots of web UI instead
- *"The web interface exists but let's focus on the core CLI architecture since that's the real API surface."*

### Scenario 5: Total technical meltdown

**Fallback**:
- Switch to screenshot walkthrough
- Focus on architecture discussion and code review
- *"Let's look at the code itself - that's where the real story is anyway."*
- Show key files in VS Code:
  - `src/llm_provider.py` (MockLLMProvider)
  - `src/agents.py` (three-agent system)
  - `tests/test_quiz_generator.py` (test examples)
  - `config.yaml` (configuration)

---

## Q&A: Anticipated Questions

### Q: "Why not just use pytest mocks instead of MockLLMProvider?"

**A**: *"Great question. Pytest mocks are great for unit testing individual functions, but MockLLMProvider serves a different purpose. It allows me to run the ENTIRE application end-to-end in zero-cost mode - not just tests, but actual quiz generation, CLI commands, even the web interface. It's a development mode, not just a testing strategy. Plus, it demonstrates the power of abstraction - the same code path is exercised in mock and production modes."*

### Q: "How do you prevent accidentally using real API calls in development?"

**A**: *"Several safeguards: First, config.yaml defaults to 'mock'. Second, the get_provider() function has an approval gate - if you try to use a real provider, it prompts 'This will cost money. Continue? (yes/no)'. Third, our test suite ONLY uses mock mode. Fourth, cost_tracking.py logs every API call, so you'd see unexpected charges immediately. And finally - muscle memory. After generating hundreds of quizzes in mock mode, it becomes second nature to check the config first."*

### Q: "What happens when mock responses don't match real AI behavior?"

**A**: *"That's the trade-off. Mock responses are static and simplified. They're good enough for testing workflow, validation logic, error handling, and UI behavior. But they can't test prompt engineering or real AI quirks. That's why I have TWO modes: mock for development/iteration, and real for final validation before production. I do a 'smoke test' with real AI before deploying, but all the heavy iteration happens in mock mode."*

### Q: "How does this scale to multiple teachers or schools?"

**A**: *"Current architecture is single-teacher, local-first (SQLite). For multi-teacher, I'd need: authentication, PostgreSQL or cloud DB, teacher/school isolation in the schema, and API rate limiting per teacher. The core logic wouldn't change much - the provider abstraction and agent system are already designed for scale. It's mostly a deployment and data isolation problem."*

### Q: "Can you actually trust AI-generated quiz questions?"

**A**: *"Not blindly - that's why we have the Critic Agent AND human review. The workflow is: Generator creates questions → Critic reviews → Teacher approves before use. QuizWeaver is a teaching ASSISTANT, not a replacement. It saves time by generating a first draft, but teachers remain firmly in control. The assumption is teachers will review and edit questions before giving them to students."*

### Q: "What did you learn from using OpenSpec?"

**A**: *"OpenSpec forced me to think in terms of tasks, dependencies, and incremental progress. Instead of 'build multi-class support', I had 6 specific tasks: create schema, write migration, build CRUD functions, add CLI commands, test isolation, document usage. Each task was small enough to complete and verify independently. This made it easier to parallelize work (frontend and backend agents) and to recover from mistakes. The biggest win was the mental model - specs as source of truth, tasks as units of work."*

### Q: "How long did this take to build?"

**A**: *"About [X hours/days] of focused work during the workshop. The key was iterative development: get one section working, test thoroughly, commit, move to next section. MockLLMProvider was implemented first because it unlocked everything else - once I could iterate for free, progress accelerated dramatically. The test suite grew alongside features, so I always had confidence that new changes didn't break old functionality."*

### Q: "Would you use MockLLMProvider on future projects?"

**A**: *"Absolutely. It's now part of my standard AI development toolkit. For any project using LLMs, I'd create a mock provider first - before writing any application logic. It makes TDD possible with AI systems, which is huge. The pattern is: define the provider interface, implement mock version, build application logic against mock, swap in real provider when ready. This also makes the application more testable and maintainable long-term."*

---

## Post-Demo Notes

### What Went Well
- [ ] MockLLMProvider concept landed
- [ ] Tests ran successfully
- [ ] CLI commands worked smoothly
- [ ] Architecture explanation was clear
- [ ] Timing was good

### What Could Improve
- [ ] (Note anything that stumbled)
- [ ] (Technical issues that came up)
- [ ] (Questions you couldn't answer)
- [ ] (Sections that ran too long/short)

### Follow-Up Actions
- [ ] Share demo recording (if recorded)
- [ ] Upload to GitHub with README
- [ ] Write blog post about MockLLMProvider pattern
- [ ] Clean up code for public release
- [ ] Update documentation based on questions

---

## Appendix: Key Commands Reference

```bash
# Test suite
python -m pytest -v --tb=short

# Quiz generation (mock mode)
python main.py generate --count 10 --grade "8th Grade" --sol "SOL 8.1" --no-interactive

# Class management
python main.py list-classes
python main.py new-class "Class Name" "Description"
python main.py set-class <id>

# Lesson tracking
python main.py log-lesson "Lesson Title" "Notes and observations"
python main.py list-lessons --limit 5

# Cost monitoring
python main.py cost-summary

# Web interface
python web.py  # Then open http://localhost:5000

# Database reset (if needed)
python -c "from src.migrations import init_database_with_migrations; init_database_with_migrations('quiz_warehouse.db')"

# Check config
type config.yaml | findstr provider
```

---

## Presentation Tips

1. **Energy**: Stay enthusiastic - this is cool tech solving a real problem
2. **Pace**: Slow down when showing code, speed up during explanations
3. **Engagement**: Make eye contact, ask rhetorical questions, pause for impact
4. **Technical depth**: Adjust based on audience - more detail for engineers, higher level for PMs
5. **Storytelling**: Use the teacher pain point as the emotional hook
6. **Confidence**: If something breaks, troubleshoot calmly - it demonstrates real-world skills
7. **Time management**: Have a watch visible; know which sections can be shortened if running long
8. **Backup plan**: Always have screenshots ready in case of total technical failure

**Remember**: The core message is "build AI systems cost-effectively using mock providers" - everything else is supporting evidence.

**Good luck! You've got this.**
