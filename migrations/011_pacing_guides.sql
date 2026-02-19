-- Migration 011: Add pacing guides tables
-- Curriculum pacing guides map standards to weeks/units across a school year.

CREATE TABLE IF NOT EXISTS pacing_guides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL REFERENCES classes(id),
    title TEXT NOT NULL,
    school_year TEXT,
    total_weeks INTEGER DEFAULT 36,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pacing_guide_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pacing_guide_id INTEGER NOT NULL REFERENCES pacing_guides(id),
    unit_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    start_week INTEGER NOT NULL,
    end_week INTEGER NOT NULL,
    standards TEXT,
    topics TEXT,
    assessment_type TEXT,
    notes TEXT
);
