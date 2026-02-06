# QuizWeaver Architecture

## System Overview

QuizWeaver is a local-first, AI-powered teaching platform built on Python + SQLite. It follows a layered architecture with clear separation between CLI, business logic, and data access.

```
                    +---------------------+
                    |     CLI (main.py)   |
                    |   argparse commands  |
                    +-----+---------+-----+
                          |         |
              +-----------+         +-----------+
              |                                 |
    +---------v---------+            +----------v----------+
    | Multi-Class Mgmt  |            | Lesson Tracking     |
    | (classroom.py)    |            | (lesson_tracker.py) |
    +---------+---------+            +----------+----------+
              |                                 |
              +----------------+----------------+
                               |
                    +----------v----------+
                    | Agentic Pipeline    |
                    | (agents.py)         |
                    | Generator + Critic  |
                    +----------+----------+
                               |
                    +----------v----------+
                    | LLM Provider Layer  |
                    | (llm_provider.py)   |
                    | Mock | Gemini | VAI |
                    +----------+----------+
                               |
                    +----------v----------+
                    | Cost Tracking       |
                    | (cost_tracking.py)  |
                    +---------------------+

    All modules use:
    +---------------------+
    | SQLAlchemy ORM      |
    | (database.py)       |
    | SQLite local DB     |
    +---------------------+
```

## Module Responsibilities

### CLI Layer (main.py)
- Parses all CLI commands via argparse
- Routes to handler functions
- Resolves active class context (--class flag or config)
- Manages database session lifecycle

### Multi-Class Management (src/classroom.py)
- CRUD operations for teacher classes/blocks
- Active class switching (writes to config.yaml)
- Class listing with lesson/quiz count aggregation

### Lesson Tracking (src/lesson_tracker.py)
- Logs lessons taught to specific classes
- Extracts topics from lesson content (keyword matching)
- Maintains assumed knowledge depth per class (1-5 scale)
- Filters lessons by date, topic, and recency

### Agentic Pipeline (src/agents.py)
- Three-agent system: Analyst, Generator, Critic
- Orchestrator manages generate-critique loop (max 3 retries)
- Enriches context with class-specific data:
  - Recent lesson logs (past 14 days)
  - Assumed knowledge with depth levels
  - Class config (grade, standards)

### LLM Provider Layer (src/llm_provider.py)
- Abstract base class with concrete implementations
- MockLLMProvider: zero-cost development (default)
- GeminiProvider: Google Gemini API
- VertexAIProvider: Google Cloud Vertex AI
- Factory function with approval gate for real providers
- Automatic cost logging on real API calls

### Cost Tracking (src/cost_tracking.py)
- Logs all real API calls to api_costs.log
- Aggregates costs by provider, day
- Enforces session rate limits (calls and dollars)
- Formats cost reports for CLI display

### Database (src/database.py)
- SQLAlchemy ORM models for all entities
- SQLite for local-first, no-server operation

## Database Schema

```
classes
  id              INTEGER PK
  name            TEXT NOT NULL
  grade_level     TEXT
  subject         TEXT
  standards       JSON        -- ["SOL 7.1", "SOL 7.2"]
  config          JSON        -- {assumed_knowledge: {...}}
  created_at      DATETIME
  updated_at      DATETIME

lesson_logs
  id              INTEGER PK
  class_id        INTEGER FK -> classes.id
  date            DATE
  content         TEXT
  topics          JSON        -- ["photosynthesis", "cells"]
  depth           INTEGER     -- 1-5
  standards_addressed JSON
  notes           TEXT
  created_at      DATETIME

quizzes
  id              INTEGER PK
  title           TEXT
  class_id        INTEGER FK -> classes.id
  status          TEXT        -- pending/generating/generated/failed
  style_profile   JSON
  created_at      DATETIME

questions
  id              INTEGER PK
  quiz_id         INTEGER FK -> quizzes.id
  question_type   TEXT        -- mc/tf/ma
  title           TEXT
  text            TEXT
  points          FLOAT
  data            JSON

lessons (ingested content)
  id              INTEGER PK
  source_file     TEXT UNIQUE
  content         TEXT
  page_data       JSON
  ingestion_method TEXT
  created_at      DATETIME

performance_data (Phase 2)
  id              INTEGER PK
  class_id        INTEGER FK -> classes.id
  quiz_id         INTEGER FK -> quizzes.id
  topic           TEXT
  avg_score       FLOAT
  weak_areas      JSON
  date            DATE
```

## Key Design Decisions

1. **Local-first**: SQLite + file-based config, no cloud dependencies for core
2. **Mock by default**: All development uses MockLLMProvider (zero cost)
3. **Approval gate**: Real API calls require explicit user consent
4. **Idempotent migrations**: Safe to run multiple times
5. **Class isolation**: Each class has independent lesson logs and knowledge tracking
6. **JSON in SQLite**: Flexible schema for config, standards, topics
