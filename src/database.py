from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

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


class Quiz(Base):
    __tablename__ = "quizzes"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    status = Column(
        String, default="pending"
    )  # pending, generating, generated, failed, complete
    style_profile = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    questions = relationship("Question", back_populates="quiz")
    feedback = relationship("FeedbackLog", back_populates="quiz")


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
