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
    __tablename__ = "lessons"
    id = Column(Integer, primary_key=True)
    source_file = Column(String, unique=True)
    content = Column(Text)
    page_data = Column(JSON)
    ingestion_method = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    assets = relationship("Asset", back_populates="lesson")


class Asset(Base):
    __tablename__ = "assets"
    id = Column(Integer, primary_key=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"))
    asset_type = Column(String)  # e.g., 'image'
    path = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    lesson = relationship("Lesson", back_populates="assets")


class Class(Base):
    """Represents a class/block that a teacher manages."""
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


class LessonLog(Base):
    """Tracks lessons taught to each class."""
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
    """Tracks class performance on assessments (placeholder for Phase 2)."""
    __tablename__ = "performance_data"
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="SET NULL"))
    topic = Column(String, nullable=False)
    avg_score = Column(Float)  # 0.0 to 1.0
    weak_areas = Column(JSON)  # Array of specific weak points
    date = Column(Date, default=date.today, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    class_obj = relationship("Class", back_populates="performance_data")
    quiz = relationship("Quiz", back_populates="performance_data")


class Quiz(Base):
    __tablename__ = "quizzes"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="SET NULL"))  # New field
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


class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    question_type = Column(String)  # mc, tf, ma, etc.
    title = Column(String)
    text = Column(Text)
    points = Column(Float)
    data = Column(JSON)  # For options, correct_index, is_true, image_ref, etc.
    quiz = relationship("Quiz", back_populates="questions")


class FeedbackLog(Base):
    __tablename__ = "feedback_logs"
    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    source = Column(String)  # 'critic_agent' or 'teacher'
    feedback_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    quiz = relationship("Quiz", back_populates="feedback")


def get_engine(db_path):
    """Returns a SQLAlchemy engine."""
    return create_engine(f"sqlite:///{db_path}")


def init_db(engine):
    """Creates all tables in the database."""
    Base.metadata.create_all(engine)


def get_session(engine):
    """Returns a new session."""
    Session = sessionmaker(bind=engine)
    return Session()
