# Mock LLM Provider

**Capability**: `mock-llm-provider`

## Overview

The Mock LLM Provider enables cost-free development and testing by simulating real LLM API behavior without making external calls. This is critical for the workshop where API spend must be minimized.

---

## ADDED Requirements

### Requirement: Mock Provider Implementation

The system SHALL provide a MockLLMProvider class that implements the same interface as real providers (GeminiProvider, VertexAIProvider) but returns fabricated responses.

#### Scenario: Mock provider used in development mode

- **WHEN** the config is set to `llm.provider: "mock"`
- **THEN** the system SHALL instantiate MockLLMProvider instead of a real provider
- **AND** all generate() calls SHALL return realistic but fabricated responses
- **AND** no external API calls SHALL be made
- **AND** no API costs SHALL be incurred

#### Scenario: Mock responses are realistic

- **WHEN** MockLLMProvider.generate() is called with json_mode=True
- **THEN** the response SHALL be valid JSON matching the expected schema
- **AND** the response SHALL contain realistic but fabricated content (e.g., quiz questions)
- **AND** the response SHALL be different each time (to simulate real LLM behavior)

#### Scenario: Mock provider matches real provider interface

- **WHEN** a test swaps MockLLMProvider for a real provider
- **THEN** no code changes SHALL be required
- **AND** all method signatures SHALL match exactly
- **AND** prepare_image_context() SHALL return a mock image object

---

### Requirement: User Approval for Real API Calls

The system SHALL require explicit user approval before making any real LLM API calls during development.

#### Scenario: Attempting real API call in dev mode

- **WHEN** a developer attempts to use a real provider (gemini, vertex) in development
- **THEN** the system SHALL prompt "This will make real API calls and incur costs. Continue? (yes/no)"
- **AND** the system SHALL only proceed if the user explicitly types "yes"
- **AND** the system SHALL log all real API calls to a cost tracking file

#### Scenario: Production mode allows real calls

- **WHEN** the config includes `llm.mode: "production"`
- **THEN** real API calls SHALL proceed without prompts
- **AND** all calls SHALL still be logged for cost tracking

---

### Requirement: Fabricated Response Library

The system SHALL maintain a library of pre-fabricated responses for common scenarios.

#### Scenario: Quiz generation with mock provider

- **WHEN** the generator agent calls llm.generate() for quiz questions
- **THEN** MockLLMProvider SHALL return a JSON array of fabricated questions
- **AND** questions SHALL be topically relevant (based on simple keyword matching)
- **AND** questions SHALL follow the expected schema (type, text, options, correct_index)

#### Scenario: Analyst agent with mock provider

- **WHEN** the analyst agent calls llm.generate() for style analysis
- **THEN** MockLLMProvider SHALL return a fabricated style profile JSON
- **AND** the profile SHALL include realistic values (e.g., image_ratio: 0.3, question_count: 20)

#### Scenario: Critic agent with mock provider

- **WHEN** the critic agent calls llm.generate() for feedback
- **THEN** MockLLMProvider SHALL return fabricated feedback
- **AND** feedback SHALL alternate between "approved" and "needs revision" (to test both paths)

---

## Non-Requirements

- Mock provider does NOT need to use actual AI or ML models
- Mock provider does NOT need to understand content semantically
- Mock responses do NOT need to be pedagogically accurate (just structurally valid)
- Mock provider does NOT need to persist state between calls (each call is independent)
