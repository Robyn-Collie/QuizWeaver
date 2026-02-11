-- Migration 008: Add question bank support
-- Adds saved_to_bank column to questions table

ALTER TABLE questions ADD COLUMN saved_to_bank INTEGER DEFAULT 0;
