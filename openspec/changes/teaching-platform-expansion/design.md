# Teaching Platform Expansion - Design

## Context

QuizWeaver currently has:
- Single-purpose architecture (quiz generation only)
- Agentic pipeline with 3 agents (Analyst, Generator, Critic)
- SQLite database with basic schema (Lessons, Quizzes, Questions)
- Vertex AI integration (but costly)
- No multi-class support
- No lesson tracking or analytics

We're expanding it into a full teaching platform while minimizing API costs during development.

---

## Goals / Non-Goals

### Goals

**Phase 1: Foundation (Workshop Day 1)**
- Implement MockLLMProvider for cost-free development
- Add multi-class database schema and basic CRUD
- Create lesson logging system (text input only)
- Build cost tracking infrastructure
- Update CLI with new commands

**Phase 2: Standards & Analytics (Post-Workshop)**
- Standards ingestion and mapping
- Performance analytics (assumed vs actual learning)
- Teacher dashboard (CLI-based)
- Graceful degradation with missing data

**Phase 3: Advanced Features (Future)**
- Voice dictation input
- Pluggable feature system
- Web-based dashboard
- Advanced privacy controls

### Non-Goals

- **NOT** building a GUI (CLI is sufficient for workshop)
- **NOT** using real APIs during development (mock only)
- **NOT** implementing every feature at once (phased approach)
- **NOT** building a multi-tenant SaaS (single-teacher, local-first)
- **NOT** automating pedagogical decisions (teacher always in control)

---

## Decisions

### Decision 1: Mock-First Development Strategy

**Problem**: Real API calls are expensive and would blow the budget during the workshop.

**Options Considered**:
1. Use real APIs with rate limiting
2. Build mock provider that simulates behavior
3. Record/replay real API responses

**Decision**: Build MockLLMProvider that implements the LLMProvider interface.

**Rationale**:
- Zero cost during development and testing
- Deterministic behavior (easier to test)
- No dependency on external services
- Forces us to design proper interfaces
- Can swap to real provider for production

**Implementation**:
- `MockLLMProvider` class in `src/llm_provider.py`
- Pre-fabricated response templates in `src/mock_responses.py`
- Config flag: `llm.provider: "mock"` (default)
- User approval required to switch to real provider

---

### Decision 2: Database Schema Extension

**Problem**: Current schema (Lessons, Quizzes, Questions) doesn't support multi-class or tracking.

**Options Considered**:
1. Add columns to existing tables (quick but messy)
2. Create new tables with proper relationships
3. Switch to a different database (PostgreSQL, etc.)

**Decision**: Extend SQLite schema with new tables, maintain backward compatibility.

**Rationale**:
- SQLite is simple, local-first, no server setup
- New tables keep concerns separated
- Existing quiz generation still works
- Easy to migrate data if needed

**New Tables**:
```sql
Classes (id, name, grade_level, subject, standards, created_at, config)
LessonLogs (id, class_id, date, content, topics, depth, standards_addressed)
Standards (id, standard_id, description, category, grade_level)
PerformanceData (id, class_id, quiz_id, topic, avg_score, weak_areas, date)
StudentCohorts (id, class_id, cohort_name, anonymized_id, metadata)
```

**Relationships**:
- Classes 1:N LessonLogs
- Classes 1:N Quizzes (add class_id to Quizzes table)
- Classes 1:N PerformanceData
- Standards M:N LessonLogs (via junction table)
- Standards M:N Quizzes (via junction table)

---

### Decision 3: CLI-First Interface (No GUI Yet)

**Problem**: Building a web dashboard would take significant time.

**Options Considered**:
1. Build web dashboard (React, Flask backend)
2. Build TUI (terminal UI with rich/textual)
3. Stick with CLI commands + formatted output

**Decision**: CLI commands with rich formatting (colors, tables).

**Rationale**:
- Faster to build (fits workshop timeline)
- Works over SSH (useful for remote teaching)
- Easier to test and automate
- Can add GUI later without changing core logic
- Teachers comfortable with CLIs (many already use git, vim, etc.)

**Commands to Add**:
```bash
python main.py new-class "7th Grade Science - Block A"
python main.py list-classes
python main.py set-class 1
python main.py log-lesson --class 1 --text "Covered photosynthesis..."
python main.py list-lessons --class 1 --last 7
python main.py dashboard --class 1
python main.py cost-summary
python main.py generate --class 1  # existing, now class-aware
```

---

### Decision 4: Assumed Knowledge Model

**Problem**: How do we represent what students "should know" based on lessons taught?

**Options Considered**:
1. Boolean flags (taught/not taught) per topic
2. Depth levels (1-5: introduced, reinforced, practiced, mastered, expert)
3. Confidence scores (probabilistic model)
4. Knowledge graphs (semantic relationships)

**Decision**: Depth levels (1-5) per topic, updated with each lesson log.

**Rationale**:
- Simple to understand and explain
- Easy to compute (rule-based, no ML needed)
- Matches teacher mental models
- Can be displayed intuitively (progress bars)
- Sufficient for workshop scope

**Rules**:
- First mention of topic → depth = 1 (introduced)
- Second mention → depth = 2 (reinforced)
- Practice/lab lesson → depth = 3 (practiced)
- Review before test → depth = 4 (mastered)
- Advanced applications → depth = 5 (expert)

Teacher can override depth manually if needed.

---

### Decision 5: Phase 1 Implementation Scope

**Problem**: This is a huge expansion. What do we build in the workshop?

**Decision**: Focus on **Mock Provider + Multi-Class + Lesson Tracking** (foundation).

**Phase 1 Scope** (Workshop Day 1):
1. ✅ MockLLMProvider implementation
2. ✅ Database schema extension (Classes, LessonLogs tables)
3. ✅ CLI commands: new-class, list-classes, set-class, log-lesson, list-lessons
4. ✅ Update generate command to be class-aware
5. ✅ Cost tracking infrastructure
6. ✅ Basic documentation updates

**Deferred to Phase 2**:
- Standards ingestion and mapping
- Performance analytics
- Dashboard view
- Privacy/anonymization layer (no real student data yet)

**Deferred to Phase 3**:
- Voice dictation
- Pluggable features
- Web GUI
- Advanced analytics

---

### Decision 6: Agent Context Enhancement

**Problem**: Agents currently receive static content. They need class history, lesson logs, and temporal context.

**Decision**: Enhance agent context dictionaries with class-specific data.

**Implementation**:
- `run_agentic_pipeline()` now receives `class_id` parameter
- Load class's recent lesson logs (last 2 weeks by default, configurable)
- Load class's standards and coverage progress
- Include assumed knowledge depth for each topic
- Pass to agents as additional context

**Analyst Agent Changes**:
- Consider lesson logs when determining question count and difficulty
- Align style profile with topics actually taught
- Note topics that need reinforcement (mentioned often but low depth)

**Generator Agent Changes**:
- Generate questions aligned with logged lessons
- Match difficulty to assumed knowledge depth
- Prioritize topics that were recently taught or marked as confusing

**Critic Agent Changes**:
- Verify questions align with class's lesson history
- Check that difficulty matches assumed knowledge
- Flag questions on topics not yet taught to this class

---

### Decision 7: Migration Strategy

**Problem**: Existing quiz_warehouse.db has data from current development.

**Options Considered**:
1. Destructive migration (drop tables, recreate)
2. Additive migration (ALTER TABLE, add columns)
3. Start fresh (ignore old data)

**Decision**: Additive migration with a migration script.

**Implementation**:
- Create `migrations/001_add_classes.sql`
- Add `class_id` column to existing Quizzes table (nullable for backward compat)
- Create new tables (Classes, LessonLogs, etc.)
- Create default class for existing quizzes: "Legacy Class (Pre-Expansion)"
- Update existing quizzes to point to default class
- Teacher can create new classes and migrate content if desired

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI Layer                           │
│  (main.py - command routing)                                │
└─────────┬───────────────────────────────────────────────────┘
          │
          ├──> new-class ──────┐
          ├──> log-lesson ──────┤
          ├──> generate ─────────┤
          ├──> dashboard ────────┤
          │                      │
          ▼                      ▼
┌─────────────────────┐  ┌──────────────────────┐
│   Classroom Module  │  │   Lesson Tracker     │
│  (classroom.py)     │  │  (lesson_tracker.py) │
│                     │  │                      │
│ - create_class()    │  │ - log_lesson()       │
│ - get_active()      │  │ - get_recent()       │
│ - switch_context()  │  │ - update_knowledge() │
└──────────┬──────────┘  └──────────┬───────────┘
           │                        │
           ├────────────────────────┤
           ▼                        ▼
┌─────────────────────────────────────────────┐
│         Database Layer (database.py)        │
│                                             │
│  Classes | LessonLogs | Standards           │
│  Quizzes | Questions  | PerformanceData     │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │  Agentic Pipeline   │
        │    (agents.py)      │
        │                     │
        │  Context includes:  │
        │  - lesson_logs      │
        │  - assumed_knowledge│
        │  - standards        │
        │  - class_config     │
        └──────────┬──────────┘
                   │
                   ├──> Analyst Agent
                   ├──> Generator Agent
                   └──> Critic Agent
                   │
                   ▼
        ┌───────────────────────┐
        │    LLM Provider       │
        │  (llm_provider.py)    │
        │                       │
        │  MockLLMProvider ─────┤  ← Phase 1 default
        │  GeminiProvider       │  ← Available but costly
        │  VertexAIProvider     │  ← Available but costly
        └───────────────────────┘
```

---

## Implementation Phases

### Phase 1: Foundation (Workshop Day 1) - 6 hours
**Milestone**: Cost-free multi-class system with lesson tracking

1. **Hours 1-2**: MockLLMProvider
   - Implement MockLLMProvider class
   - Create mock_responses.py with templates
   - Add user approval gate for real APIs
   - Test all agents work with mock provider

2. **Hours 3-4**: Database & Multi-Class
   - Extend database schema
   - Create classroom.py module
   - Implement CLI commands (new-class, list-classes, set-class)
   - Test class isolation

3. **Hours 5-6**: Lesson Tracking
   - Create lesson_tracker.py module
   - Implement log-lesson command
   - Update agent context with lesson logs
   - Test quiz generation uses class context

**Success Criteria**:
- ✅ All agents work with MockLLMProvider (zero API cost)
- ✅ Teachers can create multiple classes
- ✅ Teachers can log lessons per class
- ✅ Quiz generation uses class-specific context
- ✅ Existing functionality still works

### Phase 2: Standards & Analytics (Post-Workshop) - TBD
- Standards ingestion
- Performance data tracking
- Analytics engine
- Dashboard command

### Phase 3: Advanced Features (Future) - TBD
- Voice dictation
- Pluggable features
- Web GUI
- Advanced privacy

---

## Testing Strategy

**Unit Tests**:
- `test_mock_provider.py`: Verify mock provider matches interface, returns valid JSON
- `test_classroom.py`: Test class creation, isolation, context switching
- `test_lesson_tracker.py`: Test logging, knowledge updates, history queries
- `test_cost_tracking.py`: Verify cost logs, rate limiting

**Integration Tests**:
- `test_class_quiz_flow.py`: Create class → log lesson → generate quiz → verify context
- `test_agent_context.py`: Verify agents receive class-specific context

**Manual Testing** (Workshop):
- Create 2 classes, log different lessons, verify isolation
- Generate quizzes for each class, verify they reflect class history
- Switch to real provider, verify cost warning and logging
- Test cost limit enforcement

---

## Risks & Mitigations

**Risk**: Accidental real API usage during workshop
**Mitigation**: Default to mock provider, require explicit approval, implement rate limits

**Risk**: Database migration breaks existing functionality
**Mitigation**: Additive migration, keep backward compatibility, test with existing data

**Risk**: Scope creep (trying to build too much)
**Mitigation**: Strict phase boundaries, defer non-essential features

**Risk**: Mock provider responses don't match real provider format
**Mitigation**: Test mock provider with existing agent prompts, verify JSON schemas

---

## Open Questions

1. **Standards format**: How should we ingest SOL/SAT standards? CSV, JSON, API?
   - **Answer**: Start with JSON files in `standards/` directory. Can add API later.

2. **Lesson depth calculation**: Should we use simple rules or more sophisticated logic?
   - **Answer**: Simple rules for Phase 1. Can enhance later based on teacher feedback.

3. **Cost tracking granularity**: Per-agent, per-operation, or per-session?
   - **Answer**: Per-operation (most detailed). Can aggregate for reports.

4. **Migration timing**: When do we run the database migration?
   - **Answer**: Automatically on first run if new tables don't exist. Idempotent.
