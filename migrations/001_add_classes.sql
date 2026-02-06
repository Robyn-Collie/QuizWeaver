-- Migration: Add multi-class support to QuizWeaver
-- Description: Extends database schema for teaching platform expansion
-- Date: 2026-02-06

-- ============================================================================
-- Classes Table
-- ============================================================================
-- Represents a class/block that a teacher manages
CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    grade_level TEXT,
    subject TEXT,
    standards TEXT,  -- JSON array of standards (e.g., ["SOL 7.1", "SOL 7.2"])
    config TEXT,     -- JSON object for class-specific config (assumed_knowledge, etc.)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- LessonLogs Table
-- ============================================================================
-- Tracks lessons taught to each class
CREATE TABLE IF NOT EXISTS lesson_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    content TEXT NOT NULL,  -- Lesson content (text, markdown, or file reference)
    topics TEXT,            -- JSON array of extracted topics
    depth INTEGER DEFAULT 1, -- Depth level: 1=introduced, 2=reinforced, 3=practiced, 4=mastered, 5=expert
    standards_addressed TEXT, -- JSON array of standards covered
    notes TEXT,             -- Teacher observations/notes
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
);

-- ============================================================================
-- Standards Table (Placeholder for Phase 2)
-- ============================================================================
-- Repository of educational standards (SOL, SAT, etc.)
CREATE TABLE IF NOT EXISTS standards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_id TEXT NOT NULL UNIQUE, -- e.g., "SOL 7.1", "SAT.MATH.1"
    description TEXT,
    category TEXT,          -- e.g., "Science", "Math", "Reading"
    grade_level TEXT,       -- e.g., "7th Grade", "High School"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- PerformanceData Table (Placeholder for Phase 2)
-- ============================================================================
-- Tracks class performance on assessments
CREATE TABLE IF NOT EXISTS performance_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL,
    quiz_id INTEGER,
    topic TEXT NOT NULL,
    avg_score REAL,         -- Average score for this topic (0.0 to 1.0)
    weak_areas TEXT,        -- JSON array of specific weak points
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
    FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE SET NULL
);

-- ============================================================================
-- Extend Existing Quizzes Table (If it exists)
-- ============================================================================
-- Note: This will fail silently if quizzes table doesn't exist yet
-- That's okay - it will be created with class_id column by database.py

-- ============================================================================
-- Indexes for Performance
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_lesson_logs_class_id ON lesson_logs(class_id);
CREATE INDEX IF NOT EXISTS idx_lesson_logs_date ON lesson_logs(date);
CREATE INDEX IF NOT EXISTS idx_performance_data_class_id ON performance_data(class_id);
CREATE INDEX IF NOT EXISTS idx_performance_data_quiz_id ON performance_data(quiz_id);

-- ============================================================================
-- Create Default "Legacy Class" for Existing Data
-- ============================================================================
-- Any quizzes created before multi-class support will be assigned to this class
INSERT INTO classes (id, name, grade_level, subject, standards, config)
VALUES (
    1,
    'Legacy Class (Pre-Platform Expansion)',
    '7th Grade',
    'Science',
    '[]',
    '{}'
)
ON CONFLICT(id) DO NOTHING;

-- Note: Updating existing quizzes is handled in Python code
-- to avoid errors if quizzes table doesn't exist yet
