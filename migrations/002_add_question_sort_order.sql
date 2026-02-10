-- Add sort_order column to questions table for custom question ordering.
-- Idempotent: will fail gracefully if column already exists.
ALTER TABLE questions ADD COLUMN sort_order INTEGER DEFAULT 0;

-- Backfill existing rows: set sort_order = id so existing order is preserved.
UPDATE questions SET sort_order = id WHERE sort_order = 0 OR sort_order IS NULL;
