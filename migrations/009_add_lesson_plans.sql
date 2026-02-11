-- Migration 009: Add lesson_plans table for BL-035 Lesson Plan Generator
-- Idempotent: safe to run multiple times

CREATE TABLE IF NOT EXISTS lesson_plans (
    id INTEGER PRIMARY KEY,
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    topics TEXT,
    standards TEXT,
    grade_level TEXT,
    duration_minutes INTEGER DEFAULT 50,
    plan_data TEXT NOT NULL,
    status TEXT DEFAULT 'draft',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
