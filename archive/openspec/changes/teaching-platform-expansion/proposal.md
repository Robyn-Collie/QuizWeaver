# Teaching Platform Expansion

## Why

QuizWeaver currently focuses on a single use case: generating quiz retakes from lesson content. However, teachers need a comprehensive platform that supports their entire teaching workflow—from lesson planning and progress tracking to assessment generation and performance analytics.

The current architecture treats quiz generation as a one-off task, but teaching is an ongoing cycle where context accumulates over time. Teachers need a system that:
- **Remembers** what's been taught across multiple classes/blocks
- **Tracks** student progress toward standards (SOL, SAT, school initiatives)
- **Analyzes** performance gaps between assumed and actual learning
- **Automates** administrative burden while keeping teachers firmly in control
- **Protects** student privacy through anonymization
- **Minimizes** cost by mocking LLM calls during development and using real APIs sparingly

This expansion transforms QuizWeaver from a quiz generator into a teaching assistant platform that respects teacher autonomy while reducing cognitive load.

---

## What Changes

**1. Architecture: From Single-Task to Multi-Class Platform**
- Add multi-class/block management (separate contexts per class)
- Introduce lesson tracking system (what's been taught, when, to whom)
- Create student progress engine (anonymized tracking toward standards)
- Build performance analytics (assumed vs actual learning)

**2. Input Layer: Beyond Static Documents**
- Add voice dictation pipeline for lesson logging
- Support ongoing lesson plan ingestion (not just one-time uploads)
- Ingest standards data (SOL, SAT, school initiatives)
- Track macro performance data (class-level test results)

**3. Cost-Conscious Development Strategy**
- **Fabricate LLM responses** for all development and testing
- Create mock provider that simulates API behavior without cost
- Only use real APIs with explicit user permission
- Prefer stock images over generated ones

**4. Pluggable Feature Architecture**
- Decouple features from core engine
- Enable/disable features per teacher preference
- Support custom workflows without breaking core functionality

**5. Privacy & Ethics Layer**
- Anonymize all student data at ingestion
- Teacher approval required for all AI-generated content
- No automated decisions about students—only teacher support
- Local-first data storage (no cloud dependencies)

**6. Teacher Dashboard**
- Live view of class progress toward standards
- Performance gap identification (what to re-teach)
- Assessment generation with HITL review
- Minimal logging tolerance (system degrades gracefully)

---

## Capabilities

### New Capabilities

**`multi-class-management`**: Teachers can manage multiple classes/blocks with separate contexts, lesson histories, and progress tracking. Each class maintains its own assumed knowledge state.

**`lesson-tracking`**: System logs what's been taught (via dictation or manual entry), maintains chronological lesson history, and updates assumed student knowledge based on lessons delivered.

**`standards-alignment`**: Tracks progress toward SOL, SAT, and school initiative standards. Maps lessons and assessments to standards. Identifies coverage gaps.

**`performance-analytics`**: Compares assumed learning (from lessons taught) against actual performance (from assessment results). Highlights topics needing reinforcement.

**`dictation-input`**: Teachers can verbally log lessons taught, including materials covered, depth of coverage, and student engagement observations.

**`mock-llm-provider`**: Development-mode LLM provider that returns fabricated but realistic responses. Zero API cost. Enables full testing without external dependencies.

**`pluggable-features`**: Core platform supports feature registration, enabling/disabling. Teachers customize their workflow without code changes.

**`anonymization-layer`**: All student identifiers are anonymized at ingestion. System works with cohorts and aggregates, never individual PII.

**`graceful-degradation`**: System functions even with irregular logging. More data improves suggestions, but gaps don't break functionality.

### Modified Capabilities

**`quiz-generation`**: Expanded from "retake generator" to "assessment generator." Supports initial tests, retakes, formative assessments, and custom question sets. Now uses accumulated class context.

**`ingestion`**: No longer one-time bulk upload. Continuous ingestion of lessons, standards updates, and performance data. Maintains temporal history.

**`database-schema`**: Extended to support classes, student cohorts (anonymized), lesson logs, standards, and performance analytics.

**`interactive-review`**: Now part of broader HITL pattern. Teacher reviews all AI-generated content before student use.

---

## Impact

### Core Architecture
- `src/database.py`: Add tables for Classes, LessonLogs, Standards, PerformanceData, StudentCohorts
- `src/llm_provider.py`: Add `MockLLMProvider` for cost-free development
- `config.yaml`: Add feature flags, cost controls, multi-class config

### New Modules
- `src/classroom.py`: Multi-class management, context switching
- `src/lesson_tracker.py`: Lesson logging, assumed knowledge updates
- `src/standards.py`: Standards ingestion, mapping, progress calculation
- `src/analytics.py`: Performance gap analysis, re-teaching recommendations
- `src/dictation.py`: Voice input pipeline (initially text-based, voice later)
- `src/privacy.py`: Anonymization utilities, PII scrubbing
- `src/features.py`: Pluggable feature registry

### Modified Modules
- `main.py`: Add commands for `new-class`, `log-lesson`, `add-performance`, `dashboard`
- `src/agents.py`: Context now includes class history, standards, performance data
- `src/ingestion.py`: Continuous ingestion vs one-time batch

### Testing & Development
- `tests/test_mock_provider.py`: Verify mock provider matches real API interface
- `tests/test_classroom.py`: Multi-class isolation and context switching
- `tests/test_privacy.py`: Anonymization and PII detection

### Documentation
- `docs/ARCHITECTURE.md`: Update from "quiz generator" to "teaching platform"
- `docs/COST_STRATEGY.md`: Mock provider usage, API cost controls
- `docs/PRIVACY.md`: Data handling, anonymization approach
- `docs/TEACHER_GUIDE.md`: User-facing documentation for teachers
