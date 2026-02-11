-- Migration 009: Add accessibility preferences column to users table
-- Stores JSON preferences for dyslexia font, color blind mode, spacing, etc.

ALTER TABLE users ADD COLUMN accessibility_prefs TEXT DEFAULT '{}';
