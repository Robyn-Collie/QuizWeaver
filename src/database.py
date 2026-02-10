from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    Date,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, date

Base = declarative_base()


class Lesson(Base):
    """Represents ingested lesson content from documents.

    Attributes:
        id: Primary key.
        source_file: Path to the source document (unique).
        content: Full text content extracted from the document.
        page_data: JSON structure containing per-page content and metadata.
        ingestion_method: Method used for ingestion (e.g., 'pdf', 'docx', 'multimodal').
        created_at: Timestamp when the lesson was ingested.
        assets: Relationship to associated Asset objects (images, etc.).
    """
    __tablename__ = "lessons"
    id = Column(Integer, primary_key=True)
    source_file = Column(String, unique=True)
    content = Column(Text)
    page_data = Column(JSON)
    ingestion_method = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    assets = relationship("Asset", back_populates="lesson")


class Asset(Base):
    """Represents media assets extracted from lessons (images, diagrams, etc.).

    Attributes:
        id: Primary key.
        lesson_id: Foreign key to the parent Lesson.
        asset_type: Type of asset (e.g., 'image', 'diagram', 'chart').
        path: File system path to the extracted asset (unique).
        created_at: Timestamp when the asset was extracted.
        lesson: Relationship to the parent Lesson object.
    """
    __tablename__ = "assets"
    id = Column(Integer, primary_key=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"))
    asset_type = Column(String)  # e.g., 'image'
    path = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    lesson = relationship("Lesson", back_populates="assets")


class Class(Base):
    """Represents a class/block that a teacher manages.

    Attributes:
        id: Primary key.
        name: Display name of the class (e.g., "Block A", "Period 3").
        grade_level: Grade level of students (e.g., "8th Grade").
        subject: Subject area (e.g., "Algebra", "Biology").
        standards: JSON array of standards to track (e.g., ["SOL 7.1", "SOL 7.2"]).
        config: JSON object for class-specific configuration (assumed_knowledge, etc.).
        created_at: Timestamp when the class was created.
        updated_at: Timestamp of last update.
        lesson_logs: Relationship to LessonLog objects tracking lessons taught.
        quizzes: Relationship to Quiz objects generated for this class.
        performance_data: Relationship to PerformanceData objects for this class.
    """
    __tablename__ = "classes"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    grade_level = Column(String)
    subject = Column(String)
    standards = Column(JSON)  # Array of standards (e.g., ["SOL 7.1", "SOL 7.2"])
    config = Column(JSON)  # Class-specific config (assumed_knowledge, etc.)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lesson_logs = relationship("LessonLog", back_populates="class_obj")
    quizzes = relationship("Quiz", back_populates="class_obj")
    performance_data = relationship("PerformanceData", back_populates="class_obj")
    study_sets = relationship("StudySet", back_populates="class_obj")


class LessonLog(Base):
    """Tracks lessons taught to each class.

    Attributes:
        id: Primary key.
        class_id: Foreign key to the Class this lesson was taught to.
        date: Date the lesson was taught.
        content: Full text description of lesson content.
        topics: JSON array of extracted topics covered.
        depth: Depth of coverage (1-5 scale: introduced to expert).
        standards_addressed: JSON array of standards covered in this lesson.
        notes: Teacher observations and notes about the lesson.
        created_at: Timestamp when the log was created.
        class_obj: Relationship to the parent Class object.
    """
    __tablename__ = "lesson_logs"
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, default=date.today, nullable=False)
    content = Column(Text, nullable=False)  # Lesson content
    topics = Column(JSON)  # Array of extracted topics
    depth = Column(Integer, default=1)  # 1-5: introduced to expert
    standards_addressed = Column(JSON)  # Array of standards covered
    notes = Column(Text)  # Teacher observations/notes
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    class_obj = relationship("Class", back_populates="lesson_logs")


class PerformanceData(Base):
    """Tracks class performance on assessments (placeholder for Phase 2).

    Attributes:
        id: Primary key.
        class_id: Foreign key to the Class being assessed.
        quiz_id: Foreign key to the associated Quiz (nullable).
        topic: Topic being assessed.
        avg_score: Average score for the class (0.0 to 1.0 scale).
        weak_areas: JSON array of specific weak points identified.
        date: Date of the assessment.
        created_at: Timestamp when the performance data was recorded.
        class_obj: Relationship to the parent Class object.
        quiz: Relationship to the associated Quiz object.
    """
    __tablename__ = "performance_data"
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="SET NULL"))
    topic = Column(String, nullable=False)
    avg_score = Column(Float)  # 0.0 to 1.0
    weak_areas = Column(JSON)  # Array of specific weak points
    standard = Column(String)  # e.g., "SOL 7.1"
    source = Column(String, default="manual_entry")  # csv_upload, manual_entry, quiz_score
    sample_size = Column(Integer, default=0)  # number of students
    date = Column(Date, default=date.today, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    class_obj = relationship("Class", back_populates="performance_data")
    quiz = relationship("Quiz", back_populates="performance_data")


class Quiz(Base):
    """Represents a generated quiz.

    Attributes:
        id: Primary key.
        title: Title of the quiz.
        class_id: Foreign key to the Class this quiz is for (nullable for legacy quizzes).
        parent_quiz_id: FK to source quiz if this is a reading-level variant.
        reading_level: Reading level for variants (ell, below_grade, on_grade, advanced).
        status: Generation status (pending, generating, generated, failed, complete).
        style_profile: JSON object containing analyzed style from original quiz.
        created_at: Timestamp when the quiz was created.
        class_obj: Relationship to the parent Class object.
        questions: Relationship to Question objects in this quiz.
        feedback: Relationship to FeedbackLog objects for this quiz.
        performance_data: Relationship to PerformanceData objects for this quiz.
        parent_quiz: Relationship to the source quiz (for variants).
        variants: Relationship to variant quizzes derived from this quiz.
    """
    __tablename__ = "quizzes"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="SET NULL"))  # New field
    parent_quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="SET NULL"))
    reading_level = Column(String)  # ell, below_grade, on_grade, advanced
    status = Column(
        String, default="pending"
    )  # pending, generating, generated, failed, complete
    style_profile = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    class_obj = relationship("Class", back_populates="quizzes")
    questions = relationship("Question", back_populates="quiz")
    feedback = relationship("FeedbackLog", back_populates="quiz")
    performance_data = relationship("PerformanceData", back_populates="quiz")
    study_sets = relationship("StudySet", back_populates="quiz")
    parent_quiz = relationship("Quiz", remote_side=[id], backref="variants")


class Question(Base):
    """Represents an individual question within a quiz.

    Attributes:
        id: Primary key.
        quiz_id: Foreign key to the parent Quiz.
        question_type: Type of question (mc, tf, ma, etc.).
        title: Optional title or label for the question.
        text: The question text.
        points: Point value assigned to this question.
        data: JSON object containing question details (options, correct_index, is_true, image_ref, etc.).
        quiz: Relationship to the parent Quiz object.
    """
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    question_type = Column(String)  # mc, tf, ma, etc.
    title = Column(String)
    text = Column(Text)
    points = Column(Float)
    sort_order = Column(Integer, default=0)
    data = Column(JSON)  # For options, correct_index, is_true, image_ref, etc.
    quiz = relationship("Quiz", back_populates="questions")


class StudySet(Base):
    """Represents a set of study materials (flashcards, study guide, etc.).

    Attributes:
        id: Primary key.
        class_id: Foreign key to the Class this study set belongs to.
        quiz_id: Optional FK to a Quiz used as source material.
        title: Title of the study set.
        material_type: Type of material (flashcard, study_guide, vocabulary, review_sheet).
        status: Generation status (pending, generating, generated, failed).
        config: JSON object with generation config used.
        created_at: Timestamp when the study set was created.
        cards: Relationship to StudyCard objects with cascade delete.
        class_obj: Relationship to the parent Class object.
        quiz: Relationship to the source Quiz object.
    """
    __tablename__ = "study_sets"
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="SET NULL"))
    title = Column(String, nullable=False)
    material_type = Column(String, nullable=False)  # flashcard, study_guide, vocabulary, review_sheet
    status = Column(String, default="pending")  # pending, generating, generated, failed
    config = Column(Text)  # JSON text
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    class_obj = relationship("Class", back_populates="study_sets")
    quiz = relationship("Quiz", back_populates="study_sets")
    cards = relationship("StudyCard", back_populates="study_set", cascade="all, delete-orphan")


class StudyCard(Base):
    """Represents a single card/section within a study set.

    Attributes:
        id: Primary key.
        study_set_id: Foreign key to the parent StudySet.
        card_type: Type of card (flashcard, section, term, fact).
        sort_order: Display order within the set.
        front: Term, heading, or question side.
        back: Definition, content, or answer side.
        data: JSON text for extras (tags, examples, part_of_speech, etc.).
        study_set: Relationship to the parent StudySet object.
    """
    __tablename__ = "study_cards"
    id = Column(Integer, primary_key=True)
    study_set_id = Column(Integer, ForeignKey("study_sets.id", ondelete="CASCADE"), nullable=False)
    card_type = Column(String, nullable=False)  # flashcard, section, term, fact
    sort_order = Column(Integer, default=0)
    front = Column(Text)  # term / heading
    back = Column(Text)  # definition / content
    data = Column(Text)  # JSON text for extras

    # Relationships
    study_set = relationship("StudySet", back_populates="cards")


class FeedbackLog(Base):
    """Logs feedback on quizzes from critics or teachers.

    Attributes:
        id: Primary key.
        quiz_id: Foreign key to the Quiz being reviewed.
        source: Source of feedback ('critic_agent' or 'teacher').
        feedback_text: Full text of the feedback provided.
        created_at: Timestamp when the feedback was recorded.
        quiz: Relationship to the parent Quiz object.
    """
    __tablename__ = "feedback_logs"
    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    source = Column(String)  # 'critic_agent' or 'teacher'
    feedback_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    quiz = relationship("Quiz", back_populates="feedback")


class Rubric(Base):
    """Represents a scoring rubric aligned to a quiz.

    Attributes:
        id: Primary key.
        quiz_id: Foreign key to the Quiz this rubric is for.
        title: Title of the rubric.
        status: Generation status (pending, generating, generated, failed).
        config: JSON text with generation config used.
        created_at: Timestamp when the rubric was created.
        quiz: Relationship to the parent Quiz object.
        criteria: Relationship to RubricCriterion objects with cascade delete.
    """
    __tablename__ = "rubrics"
    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending, generating, generated, failed
    config = Column(Text)  # JSON text
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    quiz = relationship("Quiz", backref="rubrics")
    criteria = relationship("RubricCriterion", back_populates="rubric", cascade="all, delete-orphan")


class RubricCriterion(Base):
    """Represents a single criterion row within a rubric.

    Attributes:
        id: Primary key.
        rubric_id: Foreign key to the parent Rubric.
        sort_order: Display order within the rubric.
        criterion: What is being assessed (e.g., "Scientific Vocabulary").
        description: Detailed description of the criterion.
        max_points: Maximum points for this criterion.
        levels: JSON text with proficiency level descriptors
                (array of {level, label, description}).
        rubric: Relationship to the parent Rubric object.
    """
    __tablename__ = "rubric_criteria"
    id = Column(Integer, primary_key=True)
    rubric_id = Column(Integer, ForeignKey("rubrics.id", ondelete="CASCADE"), nullable=False)
    sort_order = Column(Integer, default=0)
    criterion = Column(Text, nullable=False)  # What's being assessed
    description = Column(Text)  # Detailed description
    max_points = Column(Float, default=5.0)
    levels = Column(Text)  # JSON: [{level, label, description}]

    # Relationships
    rubric = relationship("Rubric", back_populates="criteria")


def get_engine(db_path):
    """Returns a SQLAlchemy engine for the specified database.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        SQLAlchemy Engine instance connected to the database.
    """
    return create_engine(f"sqlite:///{db_path}")


def init_db(engine):
    """Creates all tables in the database if they don't exist.

    Args:
        engine: SQLAlchemy Engine instance to use for table creation.
    """
    Base.metadata.create_all(engine)


def get_session(engine):
    """Returns a new database session.

    Args:
        engine: SQLAlchemy Engine instance to bind the session to.

    Returns:
        SQLAlchemy Session instance for database operations.
    """
    Session = sessionmaker(bind=engine)
    return Session()
