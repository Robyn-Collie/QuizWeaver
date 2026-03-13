-- Migration 012: Add curriculum framework content columns to standards table
-- Stores JSON arrays of essential knowledge, understandings, and skills
-- for expanded Virginia SOL Life Science data.

ALTER TABLE standards ADD COLUMN essential_knowledge TEXT;
ALTER TABLE standards ADD COLUMN essential_understandings TEXT;
ALTER TABLE standards ADD COLUMN essential_skills TEXT;
