-- Migration 005: Extend performance_data with standard, source, sample_size columns
-- ALTER TABLE first so "no such table" is caught by the migration runner
-- before we try to create indexes.

ALTER TABLE performance_data ADD COLUMN standard TEXT;
ALTER TABLE performance_data ADD COLUMN source TEXT DEFAULT 'manual_entry';
ALTER TABLE performance_data ADD COLUMN sample_size INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_performance_data_standard ON performance_data(standard);
CREATE INDEX IF NOT EXISTS idx_performance_data_topic_date ON performance_data(topic, date);
