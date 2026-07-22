from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional
from .. import models, schemas, database
from ..limiter import limiter
from ..utils import get_grade, get_correct_threshold
from datetime import datetime
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# H4: Input validation constants
MAX_QUESTION_LENGTH = 2000
MAX_ANSWER_LENGTH = 5000
MAX_BANK_ENTRIES_PER_SUBJECT = 500


@router.get("/status")
async def get_status():
    """Returns backend health and whether the NLP model is warm."""
    from ..nlp_grading_service import is_nlp_loaded, is_nlp_model_available
    return {
        "status": "running",
        "nlp_loaded": is_nlp_loaded(),
        "nlp_available": is_nlp_model_available()
    }


@router.post("/grade")
@limiter.limit("30/minute")
async def grade_paper(
    request: Request,
    file: UploadFile = File(...),
    subject: str = Form(default=""),
    student_id: str = Form(default=""),
    total_marks: str = Form(default=None),
    db: Session = Depends(database.get_db)
):
    from ..submission_service import process_grading_submission
    
    # H1: Accept image files and PDFs. Some browsers send PDFs as
    # application/octet-stream, so validate by content type, extension, and
    # file signature after reading bytes.
    ALLOWED_CONTENT_TYPES = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf",
        "application/octet-stream",
    }
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
    
    # Check Content-Length header to prevent reading overly large files into memory.
    # The header is client-supplied and may be malformed — never let int() raise a 500.
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_FILE_SIZE:
                raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB.")
        except ValueError:
            pass  # ignore a malformed header; the post-read size check still applies

    filename_lower = (file.filename or "").lower()
    file_ext = "." + filename_lower.rsplit(".", 1)[-1] if "." in filename_lower else ""
    declared_type_allowed = file.content_type in ALLOWED_CONTENT_TYPES
    extension_allowed = file_ext in ALLOWED_EXTENSIONS
    if not declared_type_allowed and not extension_allowed:
        raise HTTPException(status_code=400, detail="Invalid file type. Only JPEG, PNG, WebP images, and PDFs are allowed.")

    file_bytes = await file.read()

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB.")

    # H5: Validate by actual file signature (magic bytes), not just the
    # client-supplied content-type/extension which can be spoofed. A trusted
    # extension is accepted as a secondary signal, but the client content_type
    # alone is no longer sufficient to pass the content check.
    is_pdf = file_bytes[:5] == b"%PDF-" or file_ext == ".pdf"
    is_image = (
        file_bytes.startswith(b"\xff\xd8\xff")              # JPEG
        or file_bytes.startswith(b"\x89PNG\r\n\x1a\n")      # PNG
        or (file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP")  # WebP
        or file_ext in {".jpg", ".jpeg", ".png", ".webp"}
    )
    if not (is_pdf or is_image):
        raise HTTPException(status_code=400, detail="Invalid file content. Upload a JPG, PNG, WebP, or PDF answer sheet.")
        
    logger.info(f"Processing file: {file.filename}, size: {len(file_bytes)} bytes")
    
    # M6: Pass optional teacher-supplied student_id to avoid non-deterministic hash IDs
    override_student_id = student_id.strip() or None

    from starlette.concurrency import run_in_threadpool
    
    # Process total marks if provided
    parsed_total_marks = None
    if total_marks and total_marks.strip():
        try:
            parsed_total_marks = float(total_marks.strip())
        except ValueError:
            pass

    return await run_in_threadpool(
        process_grading_submission, file_bytes, file.filename, subject, db, override_student_id, parsed_total_marks
    )


# H9: Rate limit on search
@router.get("/search")
@limiter.limit("30/minute")
async def search_students(request: Request, query: str, skip: int = 0, limit: int = 50, db: Session = Depends(database.get_db)):
    submissions = (
        db.query(models.Submission, models.Student)
        .join(models.Student, models.Submission.student_id == models.Student.student_id)
        .filter(
            models.Submission.status == models.SubmissionStatus.checked.value,
            or_(
                models.Student.name.ilike(f"%{query}%"),
                models.Student.student_id.ilike(f"%{query}%")
            )
        )
        .order_by(models.Submission.submitted_at.desc())
        .offset(skip).limit(limit)
        .all()
    )

    results = []
    for sub, student in submissions:
        total = float(sub.total_marks) if sub.total_marks else 0.0
        max_total = float(sub.max_total_marks) if sub.max_total_marks else 0.0
        score = (total / max_total * 100) if max_total else 0.0
        results.append({
            "id": sub.submission_id,
            "studentName": student.name,
            "rollNumber": student.student_id,
            "subject": sub.subject_name,
            "score": round(score, 2),
            "date": sub.checked_at.strftime("%Y-%m-%d") if sub.checked_at else None
        })
    return results


# H9: Rate limit on history
@router.get("/history")
@limiter.limit("30/minute")
async def get_history(request: Request, skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    submissions = (
        db.query(models.Submission, models.Student)
        .join(models.Student, models.Submission.student_id == models.Student.student_id)
        .filter(models.Submission.status == models.SubmissionStatus.checked.value)
        .order_by(models.Submission.submitted_at.desc())
        .offset(skip).limit(limit)
        .all()
    )
    results = []
    for sub, student in submissions:
        total = float(sub.total_marks) if sub.total_marks else 0.0
        max_total = float(sub.max_total_marks) if sub.max_total_marks else 0.0
        score = (total / max_total * 100) if max_total else 0.0
        results.append({
            "id": sub.submission_id,
            "studentName": student.name,
            "rollNumber": student.student_id,
            "subject": sub.subject_name,
            "score": round(score, 2),
            "date": sub.checked_at.strftime("%Y-%m-%d") if sub.checked_at else None,
            "submittedAt": sub.submitted_at.isoformat() if sub.submitted_at else None,
        })
    return results


@router.get("/result/{id}")
@limiter.limit("60/minute")
async def get_result(request: Request, id: int, db: Session = Depends(database.get_db)):
    sub = db.query(models.Submission).filter(models.Submission.submission_id == id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    student = db.query(models.Student).filter(models.Student.student_id == sub.student_id).first()
    student_name = student.name if student else "Not Detected"
    roll_number = student.student_id if student else "Not Detected"

    answers = db.query(models.Answer).filter(
        models.Answer.submission_id == sub.submission_id
    ).order_by(models.Answer.question_number).all()

    total_marks = sum(float(a.marks_obtained) for a in answers)
    max_total = sum(float(a.max_marks) for a in answers)
    score = (total_marks / max_total * 100) if max_total else 0.0
    attempted = sum(1 for a in answers if a.answer_text and a.answer_text.strip())
    correct_answers_count = sum(
        1 for a in answers if float(a.marks_obtained) >= get_correct_threshold() * float(a.max_marks)
    )

    # H5: Use shared get_grade from utils
    return {
        "id": sub.submission_id,
        "studentName": student_name,
        "rollNumber": roll_number,
        "subject": sub.subject_name,
        "score": round(score, 2),
        "totalMarks": round(total_marks, 2),
        "maxTotalMarks": round(max_total, 2),
        "grade": get_grade(score),
        "totalQuestions": len(answers),
        "attempted": attempted,
        "correctAnswers": correct_answers_count,
        "questions": [
            {
                "id": a.question_number,
                "question": a.question_text or "",
                "studentAnswer": a.answer_text or "",
                "correctAnswer": a.correct_answer_text or "",
                "score": float(a.marks_obtained),
                "maxScore": float(a.max_marks),
                "similarityScore": float(a.similarity_score) if a.similarity_score else 0.0,
                "aiFeedback": a.ai_feedback or "",
                # Trust the stored flag — a correctly-graded 0 (wrong answer) must
                # not be re-classified as "needs manual review" on re-fetch.
                "manualReviewRequired": bool(a.manual_review_required),
                "gradingMethod": a.grading_method or "unknown",
                "apiLimitReached": False,
                "fallbackReason": a.fallback_reason,
                "ocrConfidence": float(a.ocr_confidence) if a.ocr_confidence is not None else None,
            }
            for a in answers
        ],
        "date": sub.checked_at.strftime("%Y-%m-%d") if sub.checked_at else None
    }


# M9: Use SQL aggregate instead of loading all rows into memory
@router.get("/stats")
@limiter.limit("60/minute")
async def get_stats(request: Request, db: Session = Depends(database.get_db)):
    total_students = db.query(models.Student).count()
    total_papers = db.query(models.Submission).filter(
        models.Submission.status == models.SubmissionStatus.checked.value
    ).count()

    # M9: Compute average in SQL, not Python
    avg_result = db.query(
        func.avg(
            models.Submission.total_marks / func.nullif(models.Submission.max_total_marks, 0) * 100
        )
    ).filter(
        models.Submission.status == models.SubmissionStatus.checked.value
    ).scalar()
    avg_score = float(avg_result) if avg_result else 0.0

    total_submissions = db.query(models.Submission).count()
    success_rate = (total_papers / total_submissions * 100) if total_submissions else 0.0
    return {
        "totalStudents": total_students,
        "totalPapers": total_papers,
        "averageScore": round(avg_score, 2),
        "successRate": round(success_rate, 2)
    }


# M5: Derive subjects dynamically from question bank + defaults
@router.get("/subjects")
@limiter.limit("60/minute")
async def get_subjects(request: Request, db: Session = Depends(database.get_db)):
    default_subjects = {"General Science"}
    db_subjects = db.query(models.Assessment.subject).distinct().all()
    all_subjects = default_subjects | {s[0] for s in db_subjects if s[0]}
    return {"subjects": sorted(all_subjects)}


@router.post("/upload-answer-key")
@limiter.limit("20/minute")
async def upload_answer_key(
    request: Request,
    subject: str = Form(None),
    questions: str = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(database.get_db)
):
    """Upload a custom answer key either via JSON questions or a .docx template."""
    qa_list = []
    
    if file and (file.filename or '').endswith('.docx'):
        from ..template_parser import parse_template
        file_bytes = await file.read()
        parsed_data = parse_template(file_bytes)
        subject = subject or parsed_data.get('subject') or 'Untitled Key'
        qa_list = parsed_data.get('questions', [])
    elif questions and subject:
        try:
            qa_list = json.loads(questions)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid questions JSON")
        if not isinstance(qa_list, list):
            raise HTTPException(status_code=400, detail="Questions must be a JSON array")
    else:
        raise HTTPException(status_code=400, detail="Must provide either a .docx file or subject + questions JSON")

    # Find or create Assessment for this subject
    assessment = db.query(models.Assessment).filter(models.Assessment.subject.ilike(subject)).first()
    if not assessment:
        assessment = models.Assessment(subject=subject, title=subject + " Assessment", total_marks=0, num_questions=0)
        db.add(assessment)
        db.commit()
        db.refresh(assessment)

    existing_count = db.query(models.AssessmentQuestion).filter(
        models.AssessmentQuestion.assessment_id == assessment.id
    ).count()

    if existing_count + len(qa_list) > MAX_BANK_ENTRIES_PER_SUBJECT:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_BANK_ENTRIES_PER_SUBJECT} questions per subject. Currently {existing_count} exist."
        )

    added = 0
    for qa in qa_list:
        q_text = qa.get('question', '').strip()
        a_text = qa.get('answer', '').strip()
        m_marks = 10.0

        # H4: Validate length
        if not q_text:
            continue
        if len(q_text) > MAX_QUESTION_LENGTH:
            raise HTTPException(status_code=400, detail=f"Question too long (max {MAX_QUESTION_LENGTH} chars)")
        if len(a_text) > MAX_ANSWER_LENGTH:
            raise HTTPException(status_code=400, detail=f"Answer too long (max {MAX_ANSWER_LENGTH} chars)")

        # H4: Check for duplicates
        existing = db.query(models.AssessmentQuestion).filter(
            models.AssessmentQuestion.assessment_id == assessment.id,
            models.AssessmentQuestion.question_text.ilike(q_text)
        ).first()
        if existing:
            # Update existing instead of creating duplicate
            existing.model_answer = a_text if a_text else existing.model_answer
            old_marks = float(existing.max_marks or 0)
            delta = m_marks - old_marks
            assessment.total_marks = float(assessment.total_marks or 0) + delta
            existing.max_marks = m_marks
        else:
            db.add(models.AssessmentQuestion(
                assessment_id=assessment.id, 
                question_number=existing_count+added+1, 
                question_text=q_text, 
                model_answer=a_text, 
                max_marks=m_marks
            ))
            assessment.num_questions += 1
            # total_marks is a DECIMAL column — coerce to float to avoid Decimal+float TypeError
            assessment.total_marks = float(assessment.total_marks or 0) + m_marks
        added += 1

    db.commit()
    return {"added": added, "subject": subject}

from pydantic import BaseModel, ConfigDict

class ApproveAnswerPayload(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    submission_id: int
    question_number: int
    model_answer: str


class CorrectOcrPayload(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    submission_id: int
    question_number: int
    question_text: str
    answer_text: str

@router.post("/assessments/approve-answer")
@limiter.limit("30/minute")
async def approve_answer(request: Request, payload: ApproveAnswerPayload, db: Session = Depends(database.get_db)):
    """Approves and saves an AI-generated model answer, and regrades the student's answer."""
    submission = db.query(models.Submission).filter(models.Submission.submission_id == payload.submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    answer = db.query(models.Answer).filter(
        models.Answer.submission_id == payload.submission_id,
        models.Answer.question_number == payload.question_number
    ).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")

    from ..submission_service import _find_best_bank_match
    # Find the best assessment for the submission subject
    assessment = db.query(models.Assessment).filter(models.Assessment.subject.ilike(submission.subject_name)).first()
    if not assessment:
        # Create it if it doesn't exist
        assessment = models.Assessment(subject=submission.subject_name, title=submission.subject_name + " Assessment", total_marks=0, num_questions=0)
        db.add(assessment)
        db.commit()
        db.refresh(assessment)

    # Upsert AssessmentQuestion (guard against None question_text — ilike(None) always misses)
    assessment_q = None
    if answer.question_text:
        assessment_q = db.query(models.AssessmentQuestion).filter(
            models.AssessmentQuestion.assessment_id == assessment.id,
            models.AssessmentQuestion.question_text.ilike(answer.question_text)
        ).first()
    
    if assessment_q:
        assessment_q.model_answer = payload.model_answer
    else:
        new_q = models.AssessmentQuestion(
            assessment_id=assessment.id,
            question_number=assessment.num_questions + 1,
            question_text=answer.question_text,
            model_answer=payload.model_answer,
            max_marks=answer.max_marks
        )
        db.add(new_q)
        assessment.num_questions += 1
        assessment.total_marks = float(assessment.total_marks or 0) + float(answer.max_marks or 0)

    # Re-grade the student answer using the newly approved expected answer
    from ..nlp_grading_service import grade_with_answer
    
    # Store old marks to update submission total later
    old_marks = float(answer.marks_obtained)
    
    if answer.answer_text and answer.answer_text.strip():
        try:
            result = grade_with_answer(
                answer.question_text, answer.answer_text, payload.model_answer,
                max_marks=float(answer.max_marks)
            )
            answer.marks_obtained = result['marks']
            answer.similarity_score = round(result['similarity_score'], 3)
            answer.ai_feedback = result.get('ai_feedback')
            answer.correct_answer_text = payload.model_answer
            answer.manual_review_required = False
            answer.grading_method = result.get('grading_method') or 'provided_answer'
            answer.fallback_reason = None
        except Exception as e:
            logger.error(f"Regrading failed: {e}")
            raise HTTPException(status_code=500, detail="Failed to re-grade answer.")
    else:
        answer.marks_obtained = 0.0
        answer.correct_answer_text = payload.model_answer
        answer.manual_review_required = False
        answer.grading_method = 'provided_answer'
        answer.fallback_reason = None

    # Update Submission total marks
    diff = float(answer.marks_obtained) - old_marks
    submission.total_marks = float(submission.total_marks) + diff

    try:
        db.commit()
        db.refresh(answer)
    except Exception as e:
        db.rollback()
        logger.error(f"approve_answer commit failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to save changes")

    return {
        "id": answer.question_number,
        "question": answer.question_text,
        "studentAnswer": answer.answer_text,
        "correctAnswer": answer.correct_answer_text,
        "score": float(answer.marks_obtained),
        "maxScore": float(answer.max_marks),
        "similarityScore": float(answer.similarity_score) if answer.similarity_score else 0.0,
        "aiFeedback": answer.ai_feedback or "",
        "manualReviewRequired": False,
        "gradingMethod": answer.grading_method or "provided_answer",
        "apiLimitReached": False,
        "fallbackReason": answer.fallback_reason,
        "ocrConfidence": float(answer.ocr_confidence) if answer.ocr_confidence is not None else None,
    }


@router.post("/answers/correct-ocr")
@limiter.limit("30/minute")
async def correct_ocr_answer(request: Request, payload: CorrectOcrPayload, db: Session = Depends(database.get_db)):
    """Save teacher-corrected OCR text and grade only if a verified key exists."""
    submission = db.query(models.Submission).filter(models.Submission.submission_id == payload.submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    answer = db.query(models.Answer).filter(
        models.Answer.submission_id == payload.submission_id,
        models.Answer.question_number == payload.question_number
    ).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")

    question_text = payload.question_text.strip()
    answer_text = payload.answer_text.strip()
    if not question_text or not answer_text:
        raise HTTPException(status_code=400, detail="Question text and student answer are required")

    old_marks = float(answer.marks_obtained)
    answer.question_text = question_text
    answer.answer_text = answer_text
    answer.ocr_confidence = 1.0
    answer.checked_at = datetime.now()

    from ..submission_service import _find_best_bank_match
    bank_entry = _find_best_bank_match(db, question_text, submission.subject_name)

    if bank_entry:
        from ..nlp_grading_service import grade_with_answer
        result = grade_with_answer(
            question_text,
            answer_text,
            bank_entry.model_answer,
            max_marks=float(answer.max_marks)
        )
        answer.marks_obtained = result['marks']
        answer.similarity_score = round(result['similarity_score'], 3)
        answer.ai_feedback = result.get('ai_feedback')
        answer.correct_answer_text = bank_entry.model_answer
        answer.manual_review_required = bool(result.get('grading_method', '').startswith('manual_review_'))
        answer.grading_method = result.get('grading_method') or 'provided_answer'
        answer.fallback_reason = result.get('fallback_reason')
    else:
        answer.marks_obtained = 0.0
        answer.similarity_score = 0.0
        answer.ai_feedback = None
        answer.correct_answer_text = None
        answer.manual_review_required = True
        answer.grading_method = 'manual_review_missing_answer'
        answer.fallback_reason = 'No verified model answer matched the corrected question'

    diff = float(answer.marks_obtained) - old_marks
    submission.total_marks = float(submission.total_marks) + diff

    try:
        db.commit()
        db.refresh(answer)
    except Exception as e:
        db.rollback()
        logger.error(f"correct_ocr commit failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to save changes")

    return {
        "id": answer.question_number,
        "question": answer.question_text,
        "studentAnswer": answer.answer_text,
        "correctAnswer": answer.correct_answer_text or "",
        "score": float(answer.marks_obtained),
        "maxScore": float(answer.max_marks),
        "similarityScore": float(answer.similarity_score) if answer.similarity_score else 0.0,
        "aiFeedback": answer.ai_feedback or "",
        "manualReviewRequired": bool(answer.manual_review_required),
        "gradingMethod": answer.grading_method or "unknown",
        "apiLimitReached": False,
        "fallbackReason": answer.fallback_reason,
        "ocrConfidence": float(answer.ocr_confidence) if answer.ocr_confidence is not None else None,
    }



@router.get("/question-bank")
@limiter.limit("60/minute")
async def get_question_bank(request: Request, subject: str = None, db: Session = Depends(database.get_db)):
    """List all custom questions, optionally filtered by subject."""
    query = db.query(models.AssessmentQuestion).join(models.Assessment)
    if subject:
        query = query.filter(models.Assessment.subject.ilike(f"%{subject}%"))
    return [
        {"id": e.id, "subject": e.assessment.subject, "question": e.question_text, "answer": e.model_answer}
        for e in query.order_by(models.Assessment.subject, models.AssessmentQuestion.id).all()
    ]


class UpdateQuestionBankPayload(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    question_text: Optional[str] = None
    answer: Optional[str] = None        # maps to AssessmentQuestion.model_answer
    max_marks: Optional[float] = None


@router.patch("/question-bank/{entry_id}")
@limiter.limit("30/minute")
async def update_question_bank_entry(
    request: Request,
    entry_id: int,
    payload: UpdateQuestionBankPayload,
    db: Session = Depends(database.get_db),
):
    """Update a question-bank entry in place (model answer, question text, or marks)."""
    entry = db.query(models.AssessmentQuestion).filter(models.AssessmentQuestion.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    if payload.question_text is not None:
        qt = payload.question_text.strip()
        if not qt:
            raise HTTPException(status_code=400, detail="Question text cannot be empty")
        if len(qt) > MAX_QUESTION_LENGTH:
            raise HTTPException(status_code=400, detail=f"Question too long (max {MAX_QUESTION_LENGTH} chars)")
        entry.question_text = qt

    if payload.answer is not None:
        at = payload.answer.strip()
        if len(at) > MAX_ANSWER_LENGTH:
            raise HTTPException(status_code=400, detail=f"Answer too long (max {MAX_ANSWER_LENGTH} chars)")
        entry.model_answer = at  # "" is allowed → grades as manual-review until filled

    if payload.max_marks is not None:
        new_marks = float(payload.max_marks)
        if new_marks <= 0:
            raise HTTPException(status_code=400, detail="Max marks must be greater than 0")
        # Keep the parent assessment's total in sync with the change.
        if entry.assessment is not None:
            delta = new_marks - float(entry.max_marks or 0)
            entry.assessment.total_marks = float(entry.assessment.total_marks or 0) + delta
        entry.max_marks = new_marks

    db.commit()
    db.refresh(entry)
    return {
        "id": entry.id,
        "subject": entry.assessment.subject if entry.assessment else None,
        "question": entry.question_text,
        "answer": entry.model_answer,
    }


@router.delete("/question-bank/{entry_id}")
@limiter.limit("30/minute")
async def delete_question_bank_entry(request: Request, entry_id: int, db: Session = Depends(database.get_db)):
    """Delete a single question-bank entry by ID."""
    entry = db.query(models.AssessmentQuestion).filter(models.AssessmentQuestion.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    # Also update assessment totals if needed, but for simplicity just delete
    db.delete(entry)
    db.commit()
    return {"deleted": entry_id}


@router.get("/dashboard")
@limiter.limit("60/minute")
async def get_dashboard(request: Request, db: Session = Depends(database.get_db)):
    """All dashboard data in one call: recent activity, top performers, subject stats."""

    # Recent activity — last 8 checked submissions
    recent_rows = (
        db.query(models.Submission, models.Student)
        .join(models.Student, models.Submission.student_id == models.Student.student_id)
        .filter(models.Submission.status == models.SubmissionStatus.checked.value)
        .order_by(models.Submission.checked_at.desc())
        .limit(8)
        .all()
    )

    recent_activity = []
    for sub, student in recent_rows:
        total = float(sub.total_marks) if sub.total_marks else 0.0
        max_total = float(sub.max_total_marks) if sub.max_total_marks else 0.0
        score = (total / max_total * 100) if max_total else 0.0

        if sub.checked_at:
            delta = datetime.now() - sub.checked_at
            if delta.days >= 1:
                time_str = f"{delta.days}d ago"
            elif delta.seconds >= 3600:
                time_str = f"{delta.seconds // 3600}h ago"
            else:
                time_str = f"{max(1, delta.seconds // 60)}m ago"
        else:
            time_str = "Recently"

        recent_activity.append({
            "name": student.name,
            "subject": sub.subject_name,
            "score": round(score, 1),
            "time": time_str,
            "submissionId": sub.submission_id
        })

    # Top performers — highest average score across all their submissions
    performer_stats = (
        db.query(
            models.Student.name,
            func.avg(models.Submission.total_marks / func.nullif(models.Submission.max_total_marks, 0) * 100).label("avg_score"),
            func.count(models.Submission.submission_id).label("papers")
        )
        .join(models.Submission, models.Student.student_id == models.Submission.student_id)
        .filter(models.Submission.status == models.SubmissionStatus.checked.value)
        .group_by(models.Student.student_id, models.Student.name)
        .order_by(func.avg(models.Submission.total_marks / func.nullif(models.Submission.max_total_marks, 0) * 100).desc())
        .limit(5)
        .all()
    )
    
    top_performers = [
        {"name": stat.name, "score": round(float(stat.avg_score or 0), 1), "papers": stat.papers}
        for stat in performer_stats
    ]

    # Subject performance — average score and count per subject
    # Group by lower(subject_name) so "science" and "Science" merge
    subject_stats_query = (
        db.query(
            func.min(models.Submission.subject_name).label("subject_name"),
            func.avg(models.Submission.total_marks / func.nullif(models.Submission.max_total_marks, 0) * 100).label("avg_score"),
            func.count(models.Submission.submission_id).label("count")
        )
        .filter(models.Submission.status == models.SubmissionStatus.checked.value)
        .filter(func.lower(models.Submission.subject_name) == "general science")
        .group_by(func.lower(models.Submission.subject_name))
        .order_by(func.avg(models.Submission.total_marks / func.nullif(models.Submission.max_total_marks, 0) * 100).desc())
        .all()
    )

    subject_stats = [
        {"subject": stat.subject_name, "avgScore": round(float(stat.avg_score or 0), 1), "count": stat.count}
        for stat in subject_stats_query
    ]

    return {
        "recentActivity": recent_activity,
        "topPerformers": top_performers,
        "subjectStats": subject_stats
    }
