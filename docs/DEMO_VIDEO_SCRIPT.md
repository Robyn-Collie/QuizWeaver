# QuizWeaver Demo Video Script (5 Minutes)

## Video Metadata
- **Duration**: 5:00
- **Target Audience**: Educators, developers, workshop participants
- **Recording Environment**: Windows terminal + browser
- **Required Setup**: QuizWeaver installed, database initialized, Flask app ready

---

## 0:00-0:30 | INTRO: What is QuizWeaver?

### [SCENE 1: Title Card]
**On-screen text**:
```
QuizWeaver
AI-Powered Teaching Assistant Platform
Built in 6 hours with Claude Code + OpenSpec
```

### Narration:
"Hi, I'm Andre, and this is QuizWeaver - an AI-powered teaching assistant platform that helps educators manage their entire teaching workflow, from lesson planning and progress tracking to quiz generation and performance analytics.

What you're about to see was built in approximately 6 hours using Claude Code and OpenSpec, with 51 commits, 291 passing tests, and zero dollars in LLM API costs during development."

### [SCENE 2: Project Directory]
**On-screen**: File explorer showing QuizWeaver root directory
```
QuizWeaver/
├── src/
├── tests/
├── templates/
├── static/
├── openspec/
└── quiz_warehouse.db
```

---

## 0:30-1:30 | THE PROBLEM & SOLUTION

### [SCENE 3: Terminal - Cost Warning]

### Narration:
"The biggest challenge when building AI-powered applications? Cost control during development. Every API call to GPT-4, Claude, or Gemini costs real money. During rapid iteration, those costs add up fast.

QuizWeaver solves this with MockLLMProvider - a zero-cost development mode that returns fabricated but realistic LLM responses. You develop and test with mock responses, then switch to real providers only when you're ready."

### [SCENE 4: Show config.yaml]
**On-screen command**:
```bash
type config.yaml
```

**Highlight**:
```yaml
llm:
  provider: "mock"  # Zero-cost development mode
  gemini_model: "gemini-1.5-flash"
  vertex_model: "gemini-1.5-pro"
```

### Narration:
"See that? Provider is set to 'mock'. This means every quiz generation, every agent interaction, costs exactly zero dollars. When I'm ready for production, I change one line to 'gemini' or 'vertex', and I get real AI-generated content."

### [SCENE 5: Show mock_responses.py excerpt]
**On-screen command**:
```bash
type src\mock_responses.py | head -n 30
```

### Narration:
"The mock provider has pre-written responses for the Analyst agent, Generator agent, and Critic agent. These responses are realistic enough to test the entire pipeline without spending a cent."

---

## 1:30-3:00 | LIVE CLI DEMO

### [SCENE 6: Terminal - Show Help]

### Narration:
"Let's see QuizWeaver in action. First, I'll show you the command-line interface. QuizWeaver has 8 core commands."

**On-screen command**:
```bash
python main.py --help
```

**Expected output**:
```
usage: main.py [-h] {ingest,generate,new-class,list-classes,set-class,delete-class,log-lesson,list-lessons} ...

QuizWeaver - AI-Powered Teaching Assistant

positional arguments:
  {ingest,generate,new-class,list-classes,set-class,delete-class,log-lesson,list-lessons}
    ingest              Ingest content from documents
    generate            Generate a quiz
    new-class           Create a new class
    list-classes        List all classes
    set-class           Set the active class
    delete-class        Delete a class
    log-lesson          Log a lesson taught to the active class
    list-lessons        List lessons taught to a class
```

### [SCENE 7: Create a Class]

### Narration:
"Let's create a new class for this demo - 8th Grade Science, Block 2."

**On-screen command**:
```bash
python main.py new-class --name "8th Grade Science" --block "Block 2" --subject "Science" --grade "8th Grade"
```

**Expected output**:
```
[OK] Class created successfully
Class ID: 5
Name: 8th Grade Science
Block: Block 2
Subject: Science
Grade Level: 8th Grade
```

### [SCENE 8: List Classes]

**On-screen command**:
```bash
python main.py list-classes
```

**Expected output**:
```
Classes:
[1] Legacy Class (Block: N/A, Subject: N/A, Grade: N/A) [ACTIVE]
[2] AP Biology - Block A (Block: Block A, Subject: Biology, Grade: 11th Grade)
[3] Chemistry 101 (Block: Period 3, Subject: Chemistry, Grade: 10th Grade)
[4] Physics Honors (Block: Block B, Subject: Physics, Grade: 12th Grade)
[5] 8th Grade Science (Block: Block 2, Subject: Science, Grade: 8th Grade)
```

### [SCENE 9: Set Active Class]

### Narration:
"Now I'll set this as my active class. All subsequent operations will use this class context."

**On-screen command**:
```bash
python main.py set-class 5
```

**Expected output**:
```
[OK] Active class set to: 8th Grade Science (Block 2)
```

### [SCENE 10: Log a Lesson]

### Narration:
"Let's log a lesson I taught today about the water cycle - evaporation, condensation, precipitation, and collection."

**On-screen command**:
```bash
python main.py log-lesson --topics "Water cycle" "Evaporation" "Condensation" "Precipitation" --notes "Students struggled with condensation vs evaporation" --sols "SOL 6.5"
```

**Expected output**:
```
[OK] Lesson logged successfully for class: 8th Grade Science (Block 2)
Lesson ID: 12
Date: 2026-02-06
Topics: Water cycle, Evaporation, Condensation, Precipitation
SOLs: SOL 6.5
Notes: Students struggled with condensation vs evaporation
```

### [SCENE 11: List Recent Lessons]

**On-screen command**:
```bash
python main.py list-lessons --limit 3
```

**Expected output**:
```
Recent lessons for class: 8th Grade Science (Block 2)

[12] 2026-02-06
Topics: Water cycle, Evaporation, Condensation, Precipitation
SOLs: SOL 6.5
Notes: Students struggled with condensation vs evaporation

[11] 2026-02-05
Topics: States of matter, Phase changes
SOLs: SOL 6.4
Notes: Review lab safety before next week's experiment
```

### [SCENE 12: Generate a Quiz]

### Narration:
"Now the magic happens. Let's generate a quiz about the water cycle. QuizWeaver uses a three-agent system: the Analyst agent examines the style of previous quizzes, the Generator agent creates questions, and the Critic agent reviews them for quality."

**On-screen command**:
```bash
python main.py generate --count 10 --grade "8th Grade" --topic "Water Cycle" --no-interactive
```

**Expected output**:
```
[OK] Provider: MockLLMProvider (zero cost)
[OK] Active class: 8th Grade Science (Block 2)

Step 1/3: Analyzing quiz style...
[OK] Style analysis complete
  - Question count: 10
  - Image ratio: 0.2

Step 2/3: Generating questions...
[OK] Questions generated

Step 3/3: Critic review...
[OK] Critic review complete
  - 10 questions approved
  - 0 questions flagged

[OK] Quiz generation complete
[OK] Quiz saved to database (ID: 8)
[OK] PDF exported to: C:\Users\andre\projects\QuizWeaver\Quiz_Output\quiz_8_20260206_143022.pdf

Cost Summary:
  Provider: mock
  Total Cost: $0.00
  Tokens: 0 input, 0 output
```

### Narration:
"Notice: zero cost, because we're using MockLLMProvider. In production, this same command would use Gemini or Vertex AI and generate real quiz questions based on my lesson content."

---

## 3:00-4:00 | WEB UI QUICK TOUR

### [SCENE 13: Start Flask App]

### Narration:
"QuizWeaver also has a web interface built with Flask. Let me start the development server."

**On-screen command**:
```bash
python app.py
```

**Expected output**:
```
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
```

### [SCENE 14: Browser - Dashboard]
**Navigate to**: http://127.0.0.1:5000

### Narration:
"Here's the dashboard. I can see my classes, recent lessons, and a chart showing lessons taught over time. This gives me a bird's-eye view of my teaching activity."

**On-screen**: Hover over classes list, show Chart.js lessons-over-time chart

### [SCENE 15: Browser - Class Detail Page]
**Click on**: "8th Grade Science (Block 2)"

### Narration:
"Clicking into a class shows me all the lessons I've taught, the topics covered, and the SOLs addressed. I can see the assumed knowledge - what students should know based on everything I've taught so far."

**On-screen**: Scroll through lessons table, highlight "Assumed Knowledge" section

### [SCENE 16: Browser - Lesson List]
**Navigate to**: Lessons page

### Narration:
"The lessons page shows all lessons across all classes. I can filter by class, search by topic, and view detailed notes from each session."

**On-screen**: Show filter dropdown, search bar

### [SCENE 17: Browser - Generate Quiz Form]
**Navigate to**: Generate Quiz page

### Narration:
"And here's the quiz generation form - the same functionality as the CLI, but with a graphical interface. I can select a class, choose topics, set difficulty, and generate a quiz with one click."

**On-screen**: Show form fields (class selector, topic, grade, question count)

---

## 4:00-4:30 | TEST SUITE & STATS

### [SCENE 18: Terminal - Run Tests]

### Narration:
"Let's talk about testing. QuizWeaver has 291 passing tests covering every module - database schema, agent pipeline, cost tracking, classroom management, lesson logging, and the web interface."

**On-screen command**:
```bash
python -m pytest --tb=no -q
```

**Expected output** (scroll through):
```
............................................................. [  5%]
............................................................. [ 10%]
............................................................. [ 15%]
...
291 passed in 12.34s
```

### [SCENE 19: Show Test Coverage]

**On-screen command**:
```bash
dir tests
```

**Expected output**:
```
 Directory of C:\Users\andre\projects\QuizWeaver\tests

test_agents.py
test_classroom.py
test_cost_tracking.py
test_crud_helpers.py
test_database_schema.py
test_e2e_multi_class.py
test_lesson_tracker.py
test_mock_provider.py
test_quiz_generator.py
test_web.py
```

### Narration:
"Every module has comprehensive unit tests. The MockLLMProvider means I can test the entire AI pipeline without spending money or waiting for API calls. Tests run in seconds, not minutes."

### [SCENE 20: Show Git Log]

**On-screen command**:
```bash
git log --oneline | head -n 15
```

**Expected output**:
```
0312866 feat: Add basic authentication with login/logout and route protection
7290628 feat: Add Chart.js lessons-over-time chart to dashboard
69c64c1 feat: Add quiz generation page with form and MockLLMProvider integration
b4f6128 feat: Add multi-agent orchestration prompts for concurrent development
6a7607f test: Add edge case and migration helper tests (38 new tests)
...
```

### Narration:
"51 commits. Each one represents a small, tested, working increment. This is the power of spec-driven development with OpenSpec - clear tasks, incremental progress, continuous validation."

---

## 4:30-5:00 | CLOSING & KEY TAKEAWAYS

### [SCENE 21: Terminal - Project Stats]

**On-screen text overlay**:
```
QuizWeaver by the Numbers
─────────────────────────
  291 tests passing
   51 commits
    8 CLI commands
    3 AI agents (Analyst, Generator, Critic)
    6 hours development time
   $0 LLM API costs during development
```

### Narration:
"Let's recap what you just saw.

QuizWeaver is a production-ready teaching assistant platform with multi-class management, lesson tracking, automated quiz generation, cost tracking, and both CLI and web interfaces.

It was built in approximately 6 hours using Claude Code and OpenSpec, with test-driven development and zero LLM API costs thanks to MockLLMProvider.

The three-agent system - Analyst, Generator, and Critic - works together to create quizzes that match your teaching style, align with your standards, and maintain high quality.

Everything is local-first. Your student data stays on your machine. SQLite database, no cloud dependencies, GDPR-compliant by design."

### [SCENE 22: Code Editor - Show Architecture]

**On-screen**: Open docs/ARCHITECTURE.md or show project structure

### Narration:
"The architecture is clean and modular. Each component has a single responsibility. The LLM provider abstraction means you can swap between Mock, Gemini, Vertex AI, or add your own provider with minimal changes.

Cost tracking is built in from day one. Every API call is logged, rate limits are enforced, and you get detailed cost reports."

### [SCENE 23: Terminal - Final Message]

**On-screen text**:
```
Want to build AI apps without breaking the bank?

1. Use provider abstractions (Mock, Real)
2. Test with zero-cost mocks
3. Track every API call
4. Use spec-driven development

QuizWeaver is open source.
Try it. Break it. Learn from it.

github.com/yourusername/QuizWeaver
```

### Narration:
"If you're building AI-powered applications, learn from QuizWeaver's approach: use provider abstractions, test with mocks, track costs obsessively, and develop incrementally with specs.

Thanks for watching. The code is open source - try it, break it, learn from it. Happy building."

### [SCENE 24: Fade to Black]

**On-screen text**:
```
QuizWeaver
Built with Claude Code + OpenSpec

Made with [OK] by Andre
2026
```

**[END]**

---

## Recording Checklist

### Pre-Recording Setup
- [ ] Clean terminal (clear history)
- [ ] Reset database to fresh state with sample data
- [ ] Verify config.yaml has `provider: "mock"`
- [ ] Close unnecessary applications
- [ ] Set terminal font size to 14pt+ for readability
- [ ] Test screen recording software (OBS, Camtasia, etc.)
- [ ] Prepare second monitor for script reference

### Commands to Prepare
- [ ] Create sample classes (run before recording, or show live)
- [ ] Log sample lessons (run before recording, or show live)
- [ ] Generate at least one quiz beforehand for style analysis
- [ ] Ensure Flask app runs without errors

### Post-Production Notes
- Add background music (subtle, non-distracting)
- Use zoom/highlight for important terminal output
- Add text overlays for key stats (0 cost, 291 tests, etc.)
- Include captions for accessibility
- Add chapter markers at each timestamp
- Export at 1080p minimum resolution

### Accessibility
- All commands typed slowly and clearly
- Terminal output given time to be read
- Narration describes visual elements
- High contrast terminal theme (white on black or black on white)
- No rapid transitions or flashing

---

## Alternate 3-Minute Version (Fast Track)

If you need a shorter demo, use this condensed structure:

### 0:00-0:20 | Intro + Problem
- What is QuizWeaver? (10 sec)
- The cost problem (10 sec)

### 0:20-1:00 | MockLLMProvider Solution
- Show config.yaml
- Explain zero-cost development

### 1:00-2:00 | Live Demo
- Create class (15 sec)
- Log lesson (15 sec)
- Generate quiz (30 sec)

### 2:00-2:40 | Web UI Quick Tour
- Dashboard (10 sec)
- Class detail (10 sec)
- Quiz generation form (20 sec)

### 2:40-3:00 | Closing Stats
- 291 tests, $0 cost, 6 hours
- Call to action

---

## Troubleshooting Common Recording Issues

### Terminal Output Too Fast
- Add `timeout 2` (Windows) or `sleep 2` (Linux/Mac) between commands
- Use `| more` to paginate long output

### Database Locked Errors
- Run `engine.dispose()` in Python before commands
- Close DB Browser for SQLite if open

### Flask App Won't Start
- Check port 5000 not in use: `netstat -ano | findstr :5000`
- Use alternate port: `python app.py --port 5001`

### Mock Responses Not Working
- Verify `config.yaml` has `provider: "mock"`
- Check `src/mock_responses.py` exists
- Run `python -c "from src.llm_provider import MockLLMProvider; print(MockLLMProvider().generate('test', json_mode=False))"` to test

### Git Log Shows Unexpected Commits
- Use `git log --oneline --since="2026-02-01"` to filter recent commits
- Create a demo branch with curated commits if needed

---

## Customization Tips

### For Educators
- Use real class names, subjects (anonymize student data)
- Show actual lesson content from your teaching
- Generate quiz on topic you recently taught

### For Developers
- Deep dive into `src/agents.py` code
- Show test suite in detail (run pytest -v)
- Explain OpenSpec workflow (openspec list, openspec status)

### For Workshop Participants
- Emphasize 6-hour development time
- Show OpenSpec task breakdown
- Highlight Claude Code's role in TDD

---

## Additional Resources to Mention

- **OpenSpec GitHub**: https://github.com/Fission-AI/OpenSpec/
- **Claude Code**: https://claude.com/claude-code
- **QuizWeaver Docs**: See README.md, CLAUDE.md, docs/ARCHITECTURE.md
- **Cost Strategy**: See docs/COST_STRATEGY.md

---

## Final Notes

This script is designed for a **polished, professional demo video** suitable for:
- Workshop presentations
- Portfolio showcases
- Educational tutorials
- Open source project promotion

The 5-minute format is ideal for attention spans while showing enough detail to be credible. The script includes natural pauses, clear narration, and visual variety (terminal, browser, code editor).

**Good luck with your recording!**
