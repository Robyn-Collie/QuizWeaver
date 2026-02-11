-- Migration 009: Expand standards table for multi-set support
-- Add standard_set column to identify which framework each standard belongs to
ALTER TABLE standards ADD COLUMN standard_set TEXT DEFAULT 'sol';

-- Update existing SOL records
UPDATE standards SET standard_set = 'sol' WHERE standard_set IS NULL OR standard_set = '';

-- Add index on standard_set for efficient filtering
CREATE INDEX IF NOT EXISTS idx_standards_standard_set ON standards(standard_set);

-- Composite index for common queries (set + subject, set + grade_band)
CREATE INDEX IF NOT EXISTS idx_standards_set_subject ON standards(standard_set, subject);
CREATE INDEX IF NOT EXISTS idx_standards_set_grade ON standards(standard_set, grade_band);
