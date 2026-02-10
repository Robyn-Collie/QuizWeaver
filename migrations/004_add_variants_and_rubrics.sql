-- Migration 004: Add reading-level variants and rubric tables
-- Creates rubrics and rubric_criteria tables
-- Adds parent_quiz_id and reading_level to quizzes table

-- Create rubrics table (before ALTER TABLE so these succeed even on bare DBs)
CREATE TABLE IF NOT EXISTS rubrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    config TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create rubric_criteria table
CREATE TABLE IF NOT EXISTS rubric_criteria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rubric_id INTEGER NOT NULL REFERENCES rubrics(id) ON DELETE CASCADE,
    sort_order INTEGER DEFAULT 0,
    criterion TEXT NOT NULL,
    description TEXT,
    max_points REAL DEFAULT 5.0,
    levels TEXT,
    FOREIGN KEY (rubric_id) REFERENCES rubrics(id) ON DELETE CASCADE
);

-- Add variant columns to quizzes table
ALTER TABLE quizzes ADD COLUMN parent_quiz_id INTEGER REFERENCES quizzes(id) ON DELETE SET NULL;
ALTER TABLE quizzes ADD COLUMN reading_level TEXT;
