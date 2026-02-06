# QuizWeaver - Teaching Platform

## Overview

QuizWeaver is an AI-powered teaching assistant platform that helps educators manage their entire teaching workflow—from lesson planning and progress tracking to assessment generation and performance analytics.

Originally a quiz retake generator, QuizWeaver is expanding into a comprehensive platform that:
- Tracks what's been taught across multiple classes/blocks
- Monitors student progress toward standards (SOL, SAT, school initiatives)
- Analyzes performance gaps between assumed and actual learning
- Automates administrative burden while keeping teachers firmly in control
- Protects student privacy through anonymization
- Minimizes cost through mock LLM providers during development

## Current Status

**Phase**: Platform Expansion (Phase 1 - Foundation)
**Active Change**: teaching-platform-expansion
**Stage**: Implementation planning complete, ready to implement

## Tech Stack

- **Language**: Python 3.9+
- **Database**: SQLite (local-first, no server needed)
- **LLM Providers**: Google Gemini, Vertex AI, Mock Provider (development)
- **CLI Framework**: argparse
- **ORM**: SQLAlchemy
- **Testing**: pytest
- **Output Formats**: PDF (reportlab), QTI (Canvas-compatible)

## Architecture

```
CLI Layer (main.py)
    ↓
Business Logic (classroom, lesson_tracker, agents)
    ↓
Database Layer (SQLAlchemy ORM)
    ↓
LLM Providers (Gemini, Vertex, Mock)
```

## Key Principles

1. **Teacher-in-Control**: All AI-generated content requires teacher approval
2. **Privacy-First**: Student data is anonymized, local-first storage
3. **Cost-Conscious**: Mock providers for development, real APIs only with permission
4. **Graceful Degradation**: System works even with irregular logging
5. **Pluggable**: Features can be enabled/disabled per teacher preference

## Development Guidelines

- **Always use MockLLMProvider** during development (zero cost)
- **No real API calls** without explicit user permission
- **Test multi-class isolation** thoroughly
- **Keep backward compatibility** with existing quiz generation
- **Document cost implications** of any feature

## Standards

- **SOL Standards**: Virginia Standards of Learning
- **SAT Standards**: College Board SAT alignment
- **School Initiatives**: Custom per-school requirements

## Project Structure

```
QuizWeaver/
├── main.py                 # CLI entry point
├── config.yaml             # Configuration
├── src/
│   ├── agents.py           # Agentic pipeline (Analyst, Generator, Critic)
│   ├── classroom.py        # Multi-class management
│   ├── lesson_tracker.py   # Lesson logging and assumed knowledge
│   ├── database.py         # SQLAlchemy models
│   ├── llm_provider.py     # LLM provider abstraction (includes MockLLMProvider)
│   ├── ingestion.py        # Content ingestion
│   ├── image_gen.py        # Image generation (Vertex Imagen)
│   ├── output.py           # PDF and QTI export
│   └── review.py           # HITL review interface
├── tests/                  # Unit and integration tests
├── prompts/                # Agent prompts
├── openspec/               # OpenSpec artifacts
│   ├── specs/              # Source of truth specs
│   ├── changes/            # Proposed changes
│   └── archive/            # Completed changes
└── docs/                   # Documentation
```

## Related Documentation

- [System Architecture](../Project_Planning/01_System_Architecture.md)
- [Implementation Roadmap](../Project_Planning/02_Implementation_Roadmap.md)
- [Agent Specifications](../Project_Planning/03_Agent_Specifications.md)
- [README.md](../README.md)

## Contact

Project maintained as part of Agentic SDLC intensive workshop preparation.
