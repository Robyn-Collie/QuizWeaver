# Multi-Class Management

**Capability**: `multi-class-management`

## Overview

Teachers manage multiple classes/blocks per day. Each class has its own context, lesson history, and student progress. The system must maintain strict separation between classes while allowing easy context switching.

---

## ADDED Requirements

### Requirement: Class Creation and Configuration

The system SHALL allow teachers to create and configure multiple classes with distinct contexts.

#### Scenario: Creating a new class

- **WHEN** a teacher runs `python main.py new-class "7th Grade Science - Block A"`
- **THEN** the system SHALL create a new Class record in the database
- **AND** the class SHALL have a unique identifier
- **AND** the class SHALL store: name, grade_level, subject, creation date
- **AND** the system SHALL confirm "Class created: 7th Grade Science - Block A (ID: 1)"

#### Scenario: Configuring class details

- **WHEN** creating a class with `--grade "7th Grade" --subject "Science" --standards "SOL 7.1,SOL 7.2"`
- **THEN** the class SHALL store the grade level, subject, and associated standards
- **AND** these SHALL be used as defaults for assessments generated for this class
- **AND** the system SHALL list the configured standards

---

### Requirement: Class Context Isolation

Each class SHALL maintain its own isolated context, preventing cross-contamination of data.

#### Scenario: Lessons are class-specific

- **WHEN** a teacher logs a lesson for "Block A"
- **THEN** that lesson SHALL only appear in Block A's context
- **AND** assessments generated for "Block B" SHALL NOT include Block A's lessons
- **AND** the database query SHALL filter by class_id

#### Scenario: Quizzes are class-specific

- **WHEN** a teacher generates a quiz for "Block A"
- **THEN** the quiz SHALL be associated with Block A's class_id
- **AND** the quiz SHALL only draw from Block A's ingested content and lesson logs
- **AND** Block A's standards progress SHALL be updated, not Block B's

#### Scenario: Performance data is class-specific

- **WHEN** a teacher uploads performance data for "Block A"
- **THEN** the analytics SHALL only compare against Block A's assumed knowledge
- **AND** recommendations SHALL be based on Block A's lesson history
- **AND** Block B's analytics SHALL remain unchanged

---

### Requirement: Active Class Context Switching

The system SHALL support switching between classes without data loss or confusion.

#### Scenario: Switching active class via CLI

- **WHEN** a teacher runs `python main.py set-class 1`
- **THEN** the system SHALL set Class ID 1 as the active context
- **AND** subsequent commands SHALL operate on Class 1 unless overridden
- **AND** the system SHALL display "Active class: 7th Grade Science - Block A"

#### Scenario: Switching active class via config

- **WHEN** config.yaml contains `active_class_id: 2`
- **THEN** all operations SHALL default to Class ID 2
- **AND** CLI operations SHALL respect the config default
- **AND** the CLI flag `--class <id>` SHALL override the config value

#### Scenario: Listing all classes

- **WHEN** a teacher runs `python main.py list-classes`
- **THEN** the system SHALL display all classes with: ID, name, grade, subject, lesson count, quiz count
- **AND** the active class SHALL be marked with a `*` indicator
- **AND** classes SHALL be sorted by most recently used

---

### Requirement: Class-Scoped Dashboard

Each class SHALL have its own dashboard view showing progress, lessons, and analytics.

#### Scenario: Viewing class dashboard

- **WHEN** a teacher runs `python main.py dashboard --class 1`
- **THEN** the system SHALL display Class 1's: name, grade, subject, standards, lesson count, quiz count, standards coverage, recent lessons, performance trends
- **AND** no data from other classes SHALL appear
- **AND** the dashboard SHALL highlight gaps in standards coverage

---

## Non-Requirements

- The system does NOT need to support simultaneous operations on multiple classes (sequential is fine)
- The system does NOT need a GUI dashboard (CLI output is sufficient for workshop)
- The system does NOT need to share content between classes (each class is independent)
