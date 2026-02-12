# Cost Controls

**Capability**: `cost-controls`

## Overview

Development and testing must minimize API costs. The system enforces strict controls to prevent accidental spend during the workshop.

---

## ADDED Requirements

### Requirement: Default to Mock Provider

The system SHALL default to the mock provider for all non-production usage.

#### Scenario: Fresh installation defaults to mock

- **WHEN** a developer runs the system for the first time
- **THEN** config.yaml SHALL default to `llm.provider: "mock"`
- **AND** no API keys SHALL be required
- **AND** the system SHALL function fully with zero external dependencies

#### Scenario: Switching to real provider requires explicit action

- **WHEN** a developer wants to use a real provider
- **THEN** they SHALL manually edit config.yaml to set `llm.provider: "gemini"` or `"vertex"`
- **AND** they SHALL set the required environment variables (GEMINI_API_KEY, etc.)
- **AND** the system SHALL warn on first real API call: "⚠️  Using real API - costs will be incurred"

---

### Requirement: Cost Tracking

All real API calls SHALL be logged with estimated costs.

#### Scenario: Logging real API calls

- **WHEN** a real provider makes an API call
- **THEN** the system SHALL log: timestamp, provider, model, input_tokens, output_tokens, estimated_cost
- **AND** the log SHALL be written to `api_costs.log`
- **AND** the log SHALL be human-readable

#### Scenario: Displaying cost summary

- **WHEN** a developer runs `python main.py cost-summary`
- **THEN** the system SHALL display: total API calls, total estimated cost, cost by agent (analyst/generator/critic), cost by day, most expensive operations
- **AND** provide a warning if costs exceed a threshold (e.g., $5)

---

### Requirement: Image Generation Cost Control

AI image generation SHALL be disabled by default, with preference for stock/placeholder images.

#### Scenario: Default image strategy

- **WHEN** generating a quiz requiring images
- **THEN** the system SHALL default to: placeholder images (zero cost)
- **AND** config option `generation.generate_ai_images: false` SHALL be the default
- **AND** config option `generation.prefer_stock_images: true` SHALL be the default

#### Scenario: Explicit approval for AI image generation

- **WHEN** a teacher enables `generation.generate_ai_images: true`
- **THEN** the system SHALL warn: "⚠️  AI image generation enabled. Each image costs ~$0.02. Continue?"
- **AND** require user confirmation before the first image generation
- **AND** track image generation costs separately in the cost log

---

### Requirement: Rate Limiting for Real APIs

The system SHALL implement rate limiting to prevent runaway costs.

#### Scenario: Max calls per session

- **WHEN** config includes `llm.max_calls_per_session: 50`
- **THEN** the system SHALL stop after 50 real API calls in a single run
- **AND** display: "Rate limit reached (50 calls). Estimated cost: $X.XX. Reset by restarting."
- **AND** prevent further real API calls until restart

#### Scenario: Max cost per session

- **WHEN** config includes `llm.max_cost_per_session: 5.00` (dollars)
- **THEN** the system SHALL stop when estimated costs exceed $5
- **AND** display: "Cost limit reached ($5.00). Use mock provider or increase limit."

---

## Non-Requirements

- Exact cost calculations are NOT required (estimates are sufficient)
- The system does NOT need to enforce hard budget limits across sessions (per-session is enough)
- The system does NOT need to integrate with billing APIs (local tracking is sufficient)
