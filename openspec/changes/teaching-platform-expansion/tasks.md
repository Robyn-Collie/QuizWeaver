# Implementation Tasks - Teaching Platform Expansion

## Phase 1: Foundation (Workshop Day 1)

### 1. MockLLMProvider Implementation

- [ ] 1.1 Create `src/mock_responses.py` with response templates
  - [ ] 1.1a Add analyst_response template (style profile JSON)
  - [ ] 1.1b Add generator_response template (quiz questions JSON array)
  - [ ] 1.1c Add critic_response template (approval/feedback JSON)
  - [ ] 1.1d Add helper function to fill templates with context keywords

- [ ] 1.2 Implement `MockLLMProvider` class in `src/llm_provider.py`
  - [ ] 1.2a Inherit from LLMProvider base class
  - [ ] 1.2b Implement `generate()` method with template selection
  - [ ] 1.2c Implement `prepare_image_context()` (return mock object)
  - [ ] 1.2d Add randomization to avoid identical responses

- [ ] 1.3 Update `get_provider()` factory function
  - [ ] 1.3a Add "mock" case to provider selection
  - [ ] 1.3b Add user approval gate for non-mock providers
  - [ ] 1.3c Display warning: "⚠️  Using real API - costs will be incurred"

- [ ] 1.4 Update `config.yaml`
  - [ ] 1.4a Set default `llm.provider: "mock"`
  - [ ] 1.4b Add `llm.mode: "development"` option
  - [ ] 1.4c Add cost control settings (max_calls_per_session, max_cost_per_session)

- [ ] 1.5 Create tests for MockLLMProvider
  - [ ] 1.5a Test mock provider returns valid JSON
  - [ ] 1.5b Test responses match expected schemas
  - [ ] 1.5c Test provider matches real provider interface
  - [ ] 1.5d Test no external calls are made

### 2. Database Schema Extension

- [ ] 2.1 Create database migration script
  - [ ] 2.1a Create `migrations/001_add_classes.sql`
  - [ ] 2.1b Add Classes table definition
  - [ ] 2.1c Add LessonLogs table definition
  - [ ] 2.1d Add Standards table definition (placeholder for Phase 2)
  - [ ] 2.1e Add PerformanceData table definition (placeholder for Phase 2)
  - [ ] 2.1f Add class_id column to Quizzes table (nullable)

- [ ] 2.2 Implement migration runner
  - [ ] 2.2a Create `src/migrations.py` with run_migrations() function
  - [ ] 2.2b Check if migration needed (detect missing tables)
  - [ ] 2.2c Execute migration SQL
  - [ ] 2.2d Create default "Legacy Class" for existing quizzes
  - [ ] 2.2e Call run_migrations() on startup in main.py

- [ ] 2.3 Update `src/database.py` with new models
  - [ ] 2.3a Add Class model (SQLAlchemy ORM)
  - [ ] 2.3b Add LessonLog model
  - [ ] 2.3c Add relationships (Class 1:N LessonLogs, Class 1:N Quizzes)
  - [ ] 2.3d Update Quiz model with class_id foreign key

- [ ] 2.4 Test database schema
  - [ ] 2.4a Test migration runs successfully on clean DB
  - [ ] 2.4b Test migration runs successfully on existing DB
  - [ ] 2.4c Test migration is idempotent (can run multiple times)
  - [ ] 2.4d Test relationships work correctly

### 3. Multi-Class Management Module

- [ ] 3.1 Create `src/classroom.py` module
  - [ ] 3.1a Implement create_class(session, name, grade, subject, standards)
  - [ ] 3.1b Implement get_class(session, class_id)
  - [ ] 3.1c Implement list_classes(session)
  - [ ] 3.1d Implement get_active_class(config) - reads from config
  - [ ] 3.1e Implement set_active_class(class_id) - updates config

- [ ] 3.2 Add CLI commands to `main.py`
  - [ ] 3.2a Add `new-class` command with argparse
  - [ ] 3.2b Add `list-classes` command
  - [ ] 3.2c Add `set-class` command
  - [ ] 3.2d Add `--class` flag to existing commands (generate, etc.)

- [ ] 3.3 Implement handle_new_class()
  - [ ] 3.3a Parse arguments (name, grade, subject, standards)
  - [ ] 3.3b Call classroom.create_class()
  - [ ] 3.3c Display confirmation with class ID and details
  - [ ] 3.3d Prompt to set as active class

- [ ] 3.4 Implement handle_list_classes()
  - [ ] 3.4a Query all classes from database
  - [ ] 3.4b Format output with ID, name, grade, lesson count, quiz count
  - [ ] 3.4c Mark active class with `*` indicator
  - [ ] 3.4d Sort by most recently used

- [ ] 3.5 Implement handle_set_class()
  - [ ] 3.5a Validate class_id exists
  - [ ] 3.5b Update config.yaml with active_class_id
  - [ ] 3.5c Display confirmation

- [ ] 3.6 Test multi-class functionality
  - [ ] 3.6a Test creating multiple classes
  - [ ] 3.6b Test class context isolation
  - [ ] 3.6c Test switching active class
  - [ ] 3.6d Test --class flag overrides config

### 4. Lesson Tracking Module

- [ ] 4.1 Create `src/lesson_tracker.py` module
  - [ ] 4.1a Implement log_lesson(session, class_id, content, topics, date)
  - [ ] 4.1b Implement get_recent_lessons(session, class_id, days=14)
  - [ ] 4.1c Implement list_lessons(session, class_id, filters)
  - [ ] 4.1d Implement update_assumed_knowledge(session, class_id, topics)

- [ ] 4.2 Implement simple topic extraction
  - [ ] 4.2a Create extract_topics(text) using keyword matching
  - [ ] 4.2b Define science topic keywords (photosynthesis, mitosis, etc.)
  - [ ] 4.2c Return list of detected topics
  - [ ] 4.2d Allow manual topic override via --topics flag

- [ ] 4.3 Implement assumed knowledge tracking
  - [ ] 4.3a Create KnowledgeState model (topic, depth, last_taught)
  - [ ] 4.3b Store as JSON in Class.config['assumed_knowledge']
  - [ ] 4.3c Increment depth on repeated topic mentions
  - [ ] 4.3d Cap depth at 5 (expert level)

- [ ] 4.4 Add CLI commands for lesson tracking
  - [ ] 4.4a Add `log-lesson` command with --text and --file options
  - [ ] 4.4b Add `list-lessons` command with filters (--last, --from, --to, --topic)
  - [ ] 4.4c Add --notes option for teacher observations

- [ ] 4.5 Implement handle_log_lesson()
  - [ ] 4.5a Parse arguments (text, file, notes, topics override)
  - [ ] 4.5b Extract topics if not provided
  - [ ] 4.5c Call lesson_tracker.log_lesson()
  - [ ] 4.5d Update assumed knowledge
  - [ ] 4.5e Display confirmation with topics detected

- [ ] 4.6 Implement handle_list_lessons()
  - [ ] 4.6a Parse filters (last N days, date range, topic)
  - [ ] 4.6b Query lesson logs
  - [ ] 4.6c Format output with date, topics, depth changes
  - [ ] 4.6d Optionally show full lesson content with --verbose

- [ ] 4.7 Test lesson tracking
  - [ ] 4.7a Test logging lessons with text input
  - [ ] 4.7b Test logging lessons with file input
  - [ ] 4.7c Test topic extraction
  - [ ] 4.7d Test assumed knowledge updates
  - [ ] 4.7e Test listing lessons with various filters

### 5. Agent Context Enhancement

- [ ] 5.1 Update `run_agentic_pipeline()` in `src/agents.py`
  - [ ] 5.1a Add class_id parameter
  - [ ] 5.1b Load recent lesson logs for class (via lesson_tracker)
  - [ ] 5.1c Load class config (grade, standards, assumed knowledge)
  - [ ] 5.1d Add to context dict: lesson_logs, assumed_knowledge, class_config

- [ ] 5.2 Update agent prompts to use class context
  - [ ] 5.2a Update `prompts/analyst_prompt.txt` to reference lesson logs
  - [ ] 5.2b Update `prompts/generator_prompt.txt` to align with taught topics
  - [ ] 5.2c Update `prompts/critic_prompt.txt` to verify alignment with class history

- [ ] 5.3 Update handle_generate() in main.py
  - [ ] 5.3a Get active_class_id or use --class flag
  - [ ] 5.3b Pass class_id to run_agentic_pipeline()
  - [ ] 5.3c Display class context being used
  - [ ] 5.3d Associate generated quiz with class_id

- [ ] 5.4 Test agent context enhancement
  - [ ] 5.4a Log lessons for a class
  - [ ] 5.4b Generate quiz for that class
  - [ ] 5.4c Verify context includes lesson logs (inspect agent inputs)
  - [ ] 5.4d Verify questions align with logged topics (manual review)

### 6. Cost Tracking Infrastructure

- [ ] 6.1 Create `src/cost_tracking.py` module
  - [ ] 6.1a Implement log_api_call(provider, model, input_tokens, output_tokens, cost)
  - [ ] 6.1b Implement get_cost_summary() to read api_costs.log
  - [ ] 6.1c Implement check_rate_limit() based on config settings
  - [ ] 6.1d Implement format_cost_report() for human-readable output

- [ ] 6.2 Integrate cost tracking with real providers
  - [ ] 6.2a Update GeminiProvider.generate() to log calls
  - [ ] 6.2b Update VertexAIProvider.generate() to log calls
  - [ ] 6.2c Estimate costs based on model pricing
  - [ ] 6.2d Write logs to api_costs.log

- [ ] 6.3 Add CLI command for cost summary
  - [ ] 6.3a Add `cost-summary` command
  - [ ] 6.3b Display total calls, total cost, cost by agent, cost by day
  - [ ] 6.3c Warn if cost exceeds threshold

- [ ] 6.4 Test cost tracking
  - [ ] 6.4a Test mock provider logs nothing
  - [ ] 6.4b Test real provider logs correctly (use test mode)
  - [ ] 6.4c Test rate limiting stops execution
  - [ ] 6.4d Test cost summary displays correctly

### 7. Documentation Updates

- [ ] 7.1 Update README.md
  - [ ] 7.1a Add "Teaching Platform" section
  - [ ] 7.1b Document new CLI commands
  - [ ] 7.1c Add multi-class workflow example
  - [ ] 7.1d Add cost control information

- [ ] 7.2 Create docs/COST_STRATEGY.md
  - [ ] 7.2a Explain MockLLMProvider approach
  - [ ] 7.2b Document how to switch to real provider
  - [ ] 7.2c Document cost tracking and limits
  - [ ] 7.2d Provide pricing estimates

- [ ] 7.3 Create docs/ARCHITECTURE.md
  - [ ] 7.3a Document platform architecture (update from quiz generator)
  - [ ] 7.3b Include architecture diagram (ASCII or Mermaid)
  - [ ] 7.3c Explain module responsibilities
  - [ ] 7.3d Document database schema

- [ ] 7.4 Update config.yaml with comments
  - [ ] 7.4a Add inline comments explaining new options
  - [ ] 7.4b Document active_class_id setting
  - [ ] 7.4c Document llm.mode and cost control settings

### 8. Integration Testing

- [ ] 8.1 Create end-to-end test scenario
  - [ ] 8.1a Create two classes (7th Grade Block A, 7th Grade Block B)
  - [ ] 8.1b Log different lessons for each class
  - [ ] 8.1c Generate quiz for Block A, verify context
  - [ ] 8.1d Generate quiz for Block B, verify isolation
  - [ ] 8.1e Verify cost tracking (using mock provider)

- [ ] 8.2 Test backward compatibility
  - [ ] 8.2a Run against existing quiz_warehouse.db
  - [ ] 8.2b Verify migration creates default class
  - [ ] 8.2c Verify old quizzes still accessible
  - [ ] 8.2d Verify generate command still works without --class flag

- [ ] 8.3 Test error handling
  - [ ] 8.3a Test invalid class_id
  - [ ] 8.3b Test missing config settings
  - [ ] 8.3c Test corrupt database
  - [ ] 8.3d Verify graceful errors with helpful messages

### 9. Final Verification

- [ ] 9.1 Run all unit tests
- [ ] 9.2 Run all integration tests
- [ ] 9.3 Test complete workflow manually
- [ ] 9.4 Verify documentation is accurate
- [ ] 9.5 Verify cost controls work (no accidental API calls)
- [ ] 9.6 Commit changes with clear message
- [ ] 9.7 Tag as "v2.0-teaching-platform-phase1"

---

## Phase 2 Tasks (Deferred)

### Standards & Analytics
- [ ] Ingest SOL/SAT standards from JSON files
- [ ] Map lessons to standards
- [ ] Track standards coverage progress
- [ ] Implement performance data ingestion
- [ ] Build analytics engine (assumed vs actual learning)
- [ ] Create dashboard command

### Privacy & Anonymization
- [ ] Implement anonymization utilities
- [ ] Create StudentCohort model
- [ ] Scrub PII from inputs

---

## Phase 3 Tasks (Future)

### Advanced Features
- [ ] Voice dictation pipeline (speech-to-text)
- [ ] Pluggable feature registry
- [ ] Web-based dashboard (React frontend)
- [ ] Advanced analytics visualizations
- [ ] Export/import class data
- [ ] Multi-teacher support (team teaching)
