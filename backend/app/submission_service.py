import hashlib
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func
from fastapi import HTTPException
from . import models
from .ocr_service import extract_text
from .utils import get_grade, get_correct_threshold
import logging

logger = logging.getLogger(__name__)

# Maximum answer length stored (Text column supports unlimited, but we cap display)
MAX_ANSWER_LENGTH = 5000


def process_grading_submission(
    file_bytes: bytes,
    filename: str,
    fallback_subject: str,
    db: Session,
    override_student_id: str = None,   # M6: teacher-supplied ID takes highest priority
    provided_total_marks: float = None, # New: user-provided total marks to scale against
):
    # 1. OCR Extraction
    ocr_result = extract_text(file_bytes, filename)
    if not ocr_result.get('success'):
        detail_parts = [
            str(detail).strip()
            for detail in ocr_result.get('details', [])
            if str(detail).strip()
        ]
        readable_details = " | ".join(detail_parts)
        message = ocr_result.get('error') or "Unknown OCR error"
        if readable_details:
            message = f"{message}. {readable_details}"

        hint = ocr_result.get('hint')
        if hint:
            message = f"{message} - {hint}"

        raise HTTPException(
            status_code=400,
            detail=f"OCR failed: {message}"
        )

    raw_text = ocr_result.get('raw_text', '')
    student_name = ocr_result.get('student_name') or "Not Detected"
    ocr_student_id = ocr_result.get('student_id')
    ocr_subject = ocr_result.get('subject')
    ocr_total_marks = ocr_result.get('total_marks')  # extracted from paper header
    qa_pairs = ocr_result.get('questions', [])

    # 2. Student Identification — priority: teacher override > OCR > hash fallback
    # M6: Hash fallback is last resort; teacher can supply ID via form field
    if override_student_id:
        student_id = override_student_id
        logger.info(f"Using teacher-supplied student_id: {student_id}")
    elif ocr_student_id:
        student_id = ocr_student_id
    else:
        student_id = "STU-" + hashlib.md5(file_bytes[:1024]).hexdigest()[:8].upper()
        logger.warning(
            f"Could not detect student ID from OCR and no override provided. "
            f"Generated fallback ID: {student_id}. "
            f"Consider supplying the student ID manually."
        )

    final_subject = ocr_subject if ocr_subject else (fallback_subject or "General")

    # H7: Use flush (not commit) so the whole submission is one atomic unit.
    # A failure during grading rolls everything back — no orphan student/
    # submission rows, and a single commit at the end persists the result.
    student = db.query(models.Student).filter_by(student_id=student_id).first()
    if not student:
        student = models.Student(student_id=student_id, name=student_name)
        db.add(student)
        db.flush()
    elif student.name == "Not Detected" and student_name != "Not Detected":
        student.name = student_name

    # 3. Create Submission — status = 'processing' until grading completes (C5)
    submission_data = models.Submission(
        student_id=student_id,
        subject_name=final_subject,
        file_path=None,  # L2: files are processed in memory, not persisted
        status=models.SubmissionStatus.processing.value,
        submitted_at=datetime.now(),
    )
    db.add(submission_data)
    db.flush()  # populates submission_id without committing

    # 4. Grading — wrapped in try/except with rollback (C6)
    try:
        use_nlp_grading = False
        try:
            from .nlp_grading_service import (
                grade_answer, grade_with_answer, grade_answers_batch,
                is_nlp_model_available
            )
            if is_nlp_model_available():
                use_nlp_grading = True
        except Exception as e:
            logger.warning(f"Could not load NLP grading service: {e}")

        total_marks = 0.0
        max_total_marks = 0.0
        graded_questions = []

        if qa_pairs:
            # Resolve the question bank for this subject ONCE (2 queries total),
            # then match every OCR'd question against the in-memory entries —
            # instead of re-running full-table scans 2-3x per question.
            bank_entries = _load_subject_bank(db, final_subject)
            bank_match_by_idx = {
                idx: _match_in_bank(bank_entries, qa.get('question_text', f'Question {idx+1}'))
                for idx, qa in enumerate(qa_pairs)
            }

            # Per-question marks for questions that DON'T match a key are derived
            # from this subject's answer key (its average per-question mark), so
            # the marks scheme follows the uploaded template instead of a fixed
            # 10.0. Falls back to 10.0 only when no key exists for the subject.
            if bank_entries:
                _bank_marks = [float(e.max_marks) for e in bank_entries if e.max_marks is not None]
                default_q_marks = (sum(_bank_marks) / len(_bank_marks)) if _bank_marks else 10.0
            else:
                default_q_marks = 10.0

            batch_results = {}   # questions WITHOUT a key (AI suggestions only)
            bank_results = {}    # questions WITH a verified key (graded)

            if use_nlp_grading:
                bank_qa = [(idx, qa, bank_match_by_idx[idx])
                           for idx, qa in enumerate(qa_pairs) if bank_match_by_idx[idx]]
                batch_qa = [(idx, qa)
                            for idx, qa in enumerate(qa_pairs) if not bank_match_by_idx[idx]]

                # Questions without a key → optional AI reference suggestion only
                if batch_qa:
                    batch_input = [qa for _, qa in batch_qa]
                    try:
                        nlp_batch = grade_answers_batch(batch_input)
                        for (orig_idx, _), nlp_result in zip(batch_qa, nlp_batch):
                            batch_results[orig_idx] = nlp_result
                    except Exception as e:
                        logger.error(f"Batch grading failed: {e}")
                        for orig_idx, _ in batch_qa:
                            batch_results[orig_idx] = None

                # Questions with a verified key → grade against it.
                if bank_qa:
                    from .nlp_grading_service import get_llm_grader, grade_with_answers_batch
                    _llm_active = get_llm_grader() is not None

                    def _grade_bank(item):
                        orig_idx, qa, entry = item
                        q_text = qa.get('question_text', f'Question {orig_idx+1}')
                        answer_clean = qa.get('answer_text', '').strip()
                        return orig_idx, grade_with_answer(
                            q_text, answer_clean, entry.model_answer, max_marks=float(entry.max_marks)
                        )

                    if _llm_active:
                        # LLM grading is network-bound and LLM-aware — grade per
                        # item (parallelized when there's more than one). Must NOT
                        # route single questions through the heuristic-only batch.
                        if len(bank_qa) > 1:
                            from concurrent.futures import ThreadPoolExecutor, as_completed
                            with ThreadPoolExecutor(max_workers=min(3, len(bank_qa))) as pool:
                                futures = [pool.submit(_grade_bank, item) for item in bank_qa]
                                for future in as_completed(futures):
                                    try:
                                        orig_idx, res = future.result()
                                        bank_results[orig_idx] = res
                                    except Exception as e:
                                        logger.error(f"Bank grading failed: {e}")
                        else:
                            try:
                                orig_idx, res = _grade_bank(bank_qa[0])
                                bank_results[orig_idx] = res
                            except Exception as e:
                                logger.error(f"Bank grading failed: {e}")
                    else:
                        # Heuristic path — grade the whole set in ONE batched
                        # SBERT pass instead of N separate calls.
                        items = [{
                            'question_text': qa.get('question_text', f'Question {orig_idx+1}'),
                            'student_answer': qa.get('answer_text', '').strip(),
                            'correct_answer': entry.model_answer,
                            'max_marks': float(entry.max_marks),
                        } for orig_idx, qa, entry in bank_qa]
                        try:
                            graded = grade_with_answers_batch(items)
                            for (orig_idx, _, _), res in zip(bank_qa, graded):
                                bank_results[orig_idx] = res
                        except Exception as e:
                            logger.error(f"Bank batch grading failed: {e}")
                            for orig_idx, _, _ in bank_qa:
                                bank_results[orig_idx] = None

            # Scaling factor uses the SAME max each question will actually use,
            # so the denominator can't drift from the per-question max.
            def _unscaled_max(idx):
                if bank_match_by_idx[idx]:
                    return float(bank_match_by_idx[idx].max_marks)
                ocr_marks = qa_pairs[idx].get('max_marks')
                if ocr_marks is not None:
                    return float(ocr_marks)
                return default_q_marks

            total_unscaled_max = sum(_unscaled_max(idx) for idx in range(len(qa_pairs)))

            # Use user-provided total marks if given, otherwise fall back to OCR-extracted value
            effective_total_marks = provided_total_marks or ocr_total_marks
            scaling_factor = 1.0
            if effective_total_marks and effective_total_marks > 0 and total_unscaled_max > 0:
                scaling_factor = effective_total_marks / total_unscaled_max

            for idx, qa in enumerate(qa_pairs):
                q_num = qa.get('question_number', idx + 1)
                q_text = qa.get('question_text', f'Question {q_num}')
                answer_clean = qa.get('answer_text', '').strip()
                entry = bank_match_by_idx[idx]

                correct_answer = ""
                similarity_score = 0.0
                # Default max comes from the bank entry when present, then OCR-extracted
                # per-question marks (e.g. [5 Marks]), then the subject's average.
                if entry:
                    max_marks = float(entry.max_marks)
                elif qa.get('max_marks') is not None:
                    max_marks = float(qa['max_marks'])
                else:
                    max_marks = default_q_marks
                marks = 0.0
                ai_feedback = None
                needs_manual_review = False
                grading_method = 'skipped'
                api_limit_reached = False
                fallback_reason = None
                ocr_confidence = qa.get('ocr_confidence')
                needs_ocr_correction = bool(qa.get('needs_teacher_correction'))

                if needs_ocr_correction:
                    needs_manual_review = True
                    grading_method = 'manual_review_ocr_uncertain'
                    fallback_reason = (
                        qa.get('parse_status')
                        or 'OCR parse confidence is too low for automatic grading'
                    )
                    ai_feedback = "Please correct the OCR question/answer before grading."
                elif use_nlp_grading and answer_clean:
                    nlp_result = bank_results.get(idx) or batch_results.get(idx)
                    if nlp_result:
                        marks = float(nlp_result.get('marks', 0))
                        max_marks = float(nlp_result.get('max_marks', max_marks))
                        correct_answer = nlp_result.get('correct_answer', '')
                        similarity_score = nlp_result.get('similarity_score', 0.0)
                        ai_feedback = nlp_result.get('ai_feedback')
                        grading_method = nlp_result.get('grading_method', 'nlp')
                        fallback_reason = nlp_result.get('fallback_reason')
                        api_limit_reached = grading_method == 'api_limit_reached'
                        if (
                            grading_method.startswith('manual_review_')
                            or grading_method == 'api_limit_reached'
                        ):
                            needs_manual_review = True
                    else:
                        needs_manual_review = True
                        grading_method = 'error'
                        fallback_reason = 'No grading result was returned'
                else:
                    needs_manual_review = True
                    grading_method = 'manual_review_empty_answer' if not answer_clean else 'manual_review_nlp_unavailable'
                    fallback_reason = 'Empty answer' if not answer_clean else 'NLP grading service unavailable'

                # M8: Increased truncation limit with warning log
                if len(answer_clean) > MAX_ANSWER_LENGTH:
                    logger.warning(f"Q{q_num} answer truncated from {len(answer_clean)} to {MAX_ANSWER_LENGTH} chars")

                graded_questions.append({
                    'question_number': q_num,
                    'question_text': q_text,
                    'student_answer': answer_clean[:MAX_ANSWER_LENGTH],
                    'correct_answer': correct_answer,
                    'marks': marks,
                    'max_marks': max_marks,
                    'similarity_score': similarity_score,
                    'ai_feedback': ai_feedback,
                    'manual_review_required': needs_manual_review,
                    'grading_method': grading_method,
                    'api_limit_reached': api_limit_reached,
                    'fallback_reason': fallback_reason,
                    'ocr_confidence': ocr_confidence,
                })

                # Scale max_marks and marks according to provided_total_marks
                scaled_max_marks = max_marks * scaling_factor
                scaled_marks = marks * scaling_factor

                db.add(models.Answer(
                    submission_id=submission_data.submission_id,
                    question_number=q_num,
                    question_text=q_text,
                    answer_text=answer_clean[:MAX_ANSWER_LENGTH],
                    marks_obtained=scaled_marks,
                    max_marks=scaled_max_marks,
                    checked_at=datetime.now(),
                    similarity_score=round(similarity_score, 3),
                    ai_feedback=ai_feedback,
                    correct_answer_text=correct_answer[:MAX_ANSWER_LENGTH] if correct_answer else None,
                    manual_review_required=needs_manual_review,
                    grading_method=grading_method,
                    fallback_reason=fallback_reason,
                    ocr_confidence=round(float(ocr_confidence), 3) if ocr_confidence is not None else None
                ))
                total_marks += scaled_marks
                max_total_marks += scaled_max_marks
        else:
            scaled_max = provided_total_marks if provided_total_marks and provided_total_marks > 0 else 10.0
            marks = 0.0
            db.add(models.Answer(
                submission_id=submission_data.submission_id,
                question_number=1,
                question_text="Extracted Content",
                answer_text=raw_text[:MAX_ANSWER_LENGTH],
                marks_obtained=marks,
                max_marks=scaled_max,
                checked_at=datetime.now(),
                manual_review_required=True,
                grading_method='manual_review_ocr_uncertain',
                fallback_reason='OCR did not produce reliable question-answer pairs',
                ocr_confidence=0.0,
            ))
            total_marks = marks
            max_total_marks = scaled_max

        # Grading succeeded — update status to 'checked'
        submission_data.total_marks = total_marks
        submission_data.max_total_marks = max_total_marks
        submission_data.status = models.SubmissionStatus.checked.value
        submission_data.checked_at = datetime.now()
        db.commit()
        db.refresh(submission_data)

    except Exception as grading_error:
        # H7/C6: The submission was only flushed, never committed, so a rollback
        # discards the student + submission + any answers as one unit — no orphan
        # 'processing'/'failed' rows accumulate from failed OCR/grading runs.
        logger.error(f"Grading failed before commit: {grading_error}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Grading failed. Please try again or contact support."
        )

    # 5. Format Response
    answers = db.query(models.Answer).filter(
        models.Answer.submission_id == submission_data.submission_id
    ).order_by(models.Answer.question_number).all()

    score = (total_marks / max_total_marks * 100) if max_total_marks > 0 else 0.0
    attempted = sum(1 for a in answers if a.answer_text and a.answer_text.strip())
    correct_answers_count = sum(
        1 for a in answers if float(a.marks_obtained) >= get_correct_threshold() * float(a.max_marks)
    )

    # Build response from committed DB answers so scores reflect scaling
    api_limit_by_qnum = {
        gq['question_number']: gq.get('api_limit_reached', False)
        for gq in graded_questions
    } if graded_questions else {}

    questions_list = [
        {
            "id": a.question_number,
            "question": a.question_text or f"Question {a.question_number}",
            "studentAnswer": a.answer_text or "",
            "correctAnswer": a.correct_answer_text or "",
            "score": float(a.marks_obtained),
            "maxScore": float(a.max_marks),
            "similarityScore": float(a.similarity_score) if a.similarity_score else 0.0,
            "aiFeedback": a.ai_feedback or "",
            "manualReviewRequired": bool(a.manual_review_required),
            "gradingMethod": a.grading_method or "unknown",
            "apiLimitReached": api_limit_by_qnum.get(a.question_number, False),
            "fallbackReason": a.fallback_reason,
            "ocrConfidence": float(a.ocr_confidence) if a.ocr_confidence is not None else None,
        }
        for a in answers
    ]

    return {
        "id": submission_data.submission_id,
        "studentName": student_name,
        "rollNumber": student_id,
        "subject": final_subject,
        "score": round(score, 2),
        "totalMarks": round(total_marks, 2),
        "maxTotalMarks": round(max_total_marks, 2),
        "grade": get_grade(score),
        "totalQuestions": len(answers),
        "attempted": attempted,
        "correctAnswers": correct_answers_count,
        "questions": questions_list,
        "date": submission_data.checked_at.strftime("%Y-%m-%d") if submission_data.checked_at else None
    }


def _load_subject_bank(db: Session, subject: str):
    """Return the AssessmentQuestion rows for the assessment whose subject best
    matches `subject`, or []. One pass over assessments + one entries query —
    intended to be called ONCE per submission, then matched in memory."""
    assessments = db.query(models.Assessment).all()

    best_assessment = None
    best_overlap = 0
    subj_lower = (subject or "").lower().strip()

    for a in assessments:
        a_subj = a.subject.lower().strip()
        if a_subj and (a_subj in subj_lower or subj_lower in a_subj):
            if len(a_subj) > best_overlap:
                best_overlap = len(a_subj)
                best_assessment = a

    if not best_assessment:
        return []

    return db.query(models.AssessmentQuestion).filter(
        models.AssessmentQuestion.assessment_id == best_assessment.id
    ).all()


def _match_in_bank(bank_entries, question_text: str):
    """Fuzzy substring match of an OCR'd question against pre-loaded bank entries.
    H3: containment both ways, longest match wins. Pure in-memory (no DB)."""
    if not bank_entries:
        return None

    q_lower = (question_text or "").lower().strip()
    if not q_lower:
        return None

    best_match = None
    best_overlap = 0
    for entry in bank_entries:
        entry_q = entry.question_text.lower().strip()
        if q_lower in entry_q or entry_q in q_lower:
            overlap = len(entry_q)
            if overlap > best_overlap:
                best_overlap = overlap
                best_match = entry

    return best_match


def _find_best_bank_match(db: Session, question_text: str, subject: str):
    """Single-question convenience wrapper (used by the approve/correct-OCR
    endpoints). For multi-question grading use _load_subject_bank + _match_in_bank
    to avoid repeated full-table scans."""
    bank_entries = _load_subject_bank(db, subject)
    return _match_in_bank(bank_entries, question_text)
