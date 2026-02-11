-- Migration 007: Add standards table for deterministic standards data
-- Note: Migration 001 created a placeholder standards table with different columns.
-- This migration adds the missing columns needed for the full standards system.

CREATE TABLE IF NOT EXISTS standards (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    subject TEXT NOT NULL,
    grade_band TEXT,
    strand TEXT,
    full_text TEXT,
    source TEXT DEFAULT 'Virginia SOL',
    version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- If the table already exists from migration 001, add missing columns
ALTER TABLE standards ADD COLUMN code TEXT;
ALTER TABLE standards ADD COLUMN subject TEXT;
ALTER TABLE standards ADD COLUMN grade_band TEXT;
ALTER TABLE standards ADD COLUMN strand TEXT;
ALTER TABLE standards ADD COLUMN full_text TEXT;
ALTER TABLE standards ADD COLUMN source TEXT DEFAULT 'Virginia SOL';
ALTER TABLE standards ADD COLUMN version TEXT;

CREATE INDEX IF NOT EXISTS idx_standards_subject ON standards(subject);
CREATE INDEX IF NOT EXISTS idx_standards_grade_band ON standards(grade_band);
CREATE INDEX IF NOT EXISTS idx_standards_code ON standards(code);
