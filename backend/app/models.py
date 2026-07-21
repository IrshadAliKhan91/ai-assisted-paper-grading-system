from sqlalchemy import Column, Integer, String, Text, DECIMAL, DateTime, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
import enum

class SubmissionStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    checked = "checked"
    failed = "failed"

class Student(Base):
    __tablename__ = "students"

    student_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    class_grade = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    submissions = relationship("Submission", back_populates="student")

class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String(100), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    total_marks = Column(DECIMAL(7, 2), nullable=False, default=100.0)
    num_questions = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())

    questions = relationship("AssessmentQuestion", back_populates="assessment", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="assessment")

class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id"), nullable=False)
    question_number = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    model_answer = Column(Text, nullable=False)
    max_marks = Column(DECIMAL(7, 2), nullable=False)

    assessment = relationship("Assessment", back_populates="questions")

class Submission(Base):
    __tablename__ = "submissions"

    submission_id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(50), ForeignKey("students.student_id"), nullable=False)
    assessment_id = Column(Integer, ForeignKey("assessments.id"), nullable=True)
    subject_name = Column(String(100), nullable=False)
    file_path = Column(Text, nullable=True)
    image_path = Column(Text, nullable=True)
    num_questions = Column(Integer, default=0)
    total_marks = Column(DECIMAL(7, 2), default=0.00)
    max_total_marks = Column(DECIMAL(7, 2), default=0.00)
    overall_feedback = Column(Text, nullable=True)
    submitted_at = Column(DateTime, server_default=func.now())
    checked_at = Column(DateTime, nullable=True)
    status = Column(String(20), default=SubmissionStatus.pending.value)

    student = relationship("Student", back_populates="submissions")
    assessment = relationship("Assessment", back_populates="submissions")
    answers = relationship("Answer", back_populates="submission", cascade="all, delete-orphan")

class Answer(Base):
    __tablename__ = "answers"

    answer_id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.submission_id"), nullable=False)
    question_number = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=True)
    answer_text = Column(Text, nullable=True)
    model_answer = Column(Text, nullable=True)
    marks_obtained = Column(DECIMAL(7, 2), default=0.00)
    max_marks = Column(DECIMAL(7, 2), nullable=False)
    checked_at = Column(DateTime, nullable=True)
    similarity_score = Column(DECIMAL(4, 3), nullable=True)
    correct_answer_text = Column(Text, nullable=True)
    ai_feedback = Column(Text, nullable=True)
    manual_review_required = Column(Boolean, nullable=False, default=False)
    grading_method = Column(String(50), nullable=True)
    fallback_reason = Column(Text, nullable=True)
    ocr_confidence = Column(DECIMAL(4, 3), nullable=True)

    submission = relationship("Submission", back_populates="answers")


