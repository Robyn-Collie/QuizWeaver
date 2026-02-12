# Lesson Tracking

**Capability**: `lesson-tracking`

## Overview

The system tracks what lessons have been taught, when, and to which class. This builds an "assumed knowledge" state for each class, which informs assessment generation and identifies topics that may need reinforcement.

---

## ADDED Requirements

### Requirement: Manual Lesson Logging

Teachers SHALL be able to log lessons taught via text input (dictation support comes later).

#### Scenario: Logging a lesson with text

- **WHEN** a teacher runs `python main.py log-lesson --class 1 --text "Covered photosynthesis: light reactions, Calvin cycle, and limiting factors. Used slides 1-15. Students seemed confused about ATP vs NADPH."`
- **THEN** the system SHALL create a LessonLog record with: class_id, date, content (text), topics (extracted), depth (inferred)
- **AND** the system SHALL confirm "Lesson logged for 7th Grade Science - Block A"
- **AND** the assumed knowledge for Class 1 SHALL be updated to include photosynthesis concepts

#### Scenario: Logging a lesson with file reference

- **WHEN** a teacher runs `python main.py log-lesson --class 1 --file "lesson_plans/photosynthesis.md" --notes "Spent extra time on ATP"`
- **THEN** the system SHALL read the file content
- **AND** create a LessonLog with both file content and notes
- **AND** link the LessonLog to any assets (images, slides) mentioned in the file

---

### Requirement: Assumed Knowledge Updates

Each logged lesson SHALL update the class's assumed knowledge state.

#### Scenario: First lesson on a topic

- **WHEN** a teacher logs the first lesson on "cell division"
- **THEN** "cell division" SHALL be added to the class's assumed knowledge
- **AND** the depth level SHALL be set to "introduced" (1/5)
- **AND** related standards SHALL be marked as "in progress"

#### Scenario: Follow-up lesson on a topic

- **WHEN** a teacher logs a second lesson on "cell division" (already taught once)
- **THEN** the depth level for "cell division" SHALL increase to "reinforced" (2/5)
- **AND** the system SHALL note the date range over which the topic was covered
- **AND** related standards SHALL move closer to "mastered"

#### Scenario: Lesson with multiple topics

- **WHEN** a teacher logs "Reviewed cell division, introduced genetics basics"
- **THEN** the system SHALL update assumed knowledge for BOTH topics
- **AND** "cell division" depth SHALL increase (review)
- **AND** "genetics basics" SHALL be added at "introduced" level

---

### Requirement: Chronological Lesson History

All lessons SHALL be stored chronologically, allowing temporal queries.

#### Scenario: Viewing recent lessons

- **WHEN** a teacher runs `python main.py list-lessons --class 1 --last 7`
- **THEN** the system SHALL display lessons from the last 7 days
- **AND** each entry SHALL show: date, topics covered, depth, standards addressed
- **AND** lessons SHALL be sorted newest-first

#### Scenario: Viewing lessons by date range

- **WHEN** a teacher runs `python main.py list-lessons --class 1 --from 2026-01-01 --to 2026-01-31`
- **THEN** the system SHALL display all lessons from January 2026
- **AND** provide a summary of topics covered and standards addressed during that period

#### Scenario: Viewing lessons by topic

- **WHEN** a teacher runs `python main.py list-lessons --class 1 --topic "photosynthesis"`
- **THEN** the system SHALL display all lessons that mentioned photosynthesis
- **AND** show the progression of depth over time
- **AND** highlight any performance data related to photosynthesis

---

### Requirement: Context for Assessment Generation

Logged lessons SHALL be used as context when generating assessments.

#### Scenario: Generating quiz from recent lessons

- **WHEN** a teacher generates a quiz for Class 1
- **THEN** the agentic pipeline SHALL receive lesson logs from the past 2 weeks (configurable)
- **AND** questions SHALL align with topics that were actually taught
- **AND** question difficulty SHALL match the depth level of each topic
- **AND** topics marked as "confused" in lesson notes SHALL be tested more thoroughly

#### Scenario: Generating retake from lesson and performance data

- **WHEN** a teacher generates a retake after poor quiz performance on "mitosis"
- **THEN** the system SHALL include: original lesson logs on mitosis, performance data showing weak areas, additional context on what was taught
- **AND** the retake SHALL focus on the specific concepts students struggled with

---

## Non-Requirements

- Voice dictation is NOT required in Phase 1 (text input is sufficient)
- Automatic topic extraction does NOT need to be perfect (keyword matching is acceptable)
- The system does NOT need to verify whether lessons were actually taught (trust the teacher)
- Lesson depth does NOT need sophisticated ML models (rule-based is fine)
