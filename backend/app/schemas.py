from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

class AnswerBase(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    question_number: int
    question_text: Optional[str] = None
    answer_text: Optional[str] = None
    model_answer: Optional[str] = None
    marks_obtained: Decimal
    max_marks: Decimal
    similarity_score: Optional[Decimal] = None
    correct_answer_text: Optional[str] = None
    ai_feedback: Optional[str] = None
    manual_review_required: bool = False
    grading_method: Optional[str] = None
    fallback_reason: Optional[str] = None
    ocr_confidence: Optional[Decimal] = None

class AnswerCreate(AnswerBase):
    pass

class Answer(AnswerBase):
    answer_id: int
    submission_id: int
    checked_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

class SubmissionBase(BaseModel):
    student_id: str
    assessment_id: Optional[int] = None
    subject_name: str
    file_path: Optional[str] = None
    image_path: Optional[str] = None
    num_questions: int = 0
    total_marks: Decimal = Decimal("0.0")
    max_total_marks: Decimal = Decimal("0.0")
    overall_feedback: Optional[str] = None

class SubmissionCreate(SubmissionBase):
    pass

class Submission(SubmissionBase):
    submission_id: int
    submitted_at: datetime
    checked_at: Optional[datetime] = None
    status: str
    answers: List[Answer] = []

    model_config = ConfigDict(from_attributes=True)

class StudentBase(BaseModel):
    student_id: str
    name: str
    class_grade: Optional[str] = None

class StudentCreate(StudentBase):
    pass

class Student(StudentBase):
    created_at: datetime
    submissions: List[Submission] = []

    model_config = ConfigDict(from_attributes=True)

class AssessmentQuestionBase(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    question_number: int
    question_text: str
    model_answer: str
    max_marks: Decimal

class AssessmentQuestionCreate(AssessmentQuestionBase):
    pass

class AssessmentQuestion(AssessmentQuestionBase):
    id: int
    assessment_id: int

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

class AssessmentBase(BaseModel):
    subject: str
    title: str
    total_marks: Decimal
    num_questions: int

class AssessmentCreate(AssessmentBase):
    questions: List[AssessmentQuestionCreate]

class Assessment(AssessmentBase):
    id: int
    created_at: datetime
    questions: List[AssessmentQuestion] = []

    model_config = ConfigDict(from_attributes=True)
