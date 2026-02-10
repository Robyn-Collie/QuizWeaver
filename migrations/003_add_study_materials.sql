-- Migration 003: Add study materials tables (study_sets, study_cards)
-- Idempotent: uses CREATE TABLE IF NOT EXISTS

CREATE TABLE IF NOT EXISTS study_sets (
    id INTEGER PRIMARY KEY,
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    quiz_id INTEGER REFERENCES quizzes(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    material_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    config TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS study_cards (
    id INTEGER PRIMARY KEY,
    study_set_id INTEGER NOT NULL REFERENCES study_sets(id) ON DELETE CASCADE,
    card_type TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0,
    front TEXT,
    back TEXT,
    data TEXT,
    FOREIGN KEY (study_set_id) REFERENCES study_sets(id) ON DELETE CASCADE
);
