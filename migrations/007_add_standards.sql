-- Migration 007: Add standards table for deterministic standards data
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

CREATE INDEX IF NOT EXISTS idx_standards_subject ON standards(subject);
CREATE INDEX IF NOT EXISTS idx_standards_grade_band ON standards(grade_band);
CREATE INDEX IF NOT EXISTS idx_standards_code ON standards(code);
