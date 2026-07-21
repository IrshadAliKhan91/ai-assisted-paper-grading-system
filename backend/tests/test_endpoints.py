"""
Endpoint test suite for the Assessment-based grading design.
Covers: status, subjects, answer-key upload + question-bank CRUD, result
retrieval (incl. aiFeedback), stats, dashboard, approve-answer 404, auth
rejection, and grade-endpoint file validation.
"""
import os
import io
import json
import pytest

# main.py refuses to import without ADMIN_PASSWORD set — provide a test default
# BEFORE importing the app.
os.environ.setdefault("ADMIN_USER", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "fairmark2026")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.database import Base, get_db
from backend.app import models

# ── In-memory DB ──────────────────────────────────────────────────────────────
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

TEST_USER = os.getenv("ADMIN_USER", "admin")
TEST_PASS = os.getenv("ADMIN_PASSWORD", "fairmark2026")
AUTH = (TEST_USER, TEST_PASS)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# ── Helpers ──────────────────────────────────────────────────────────────────
def _seed_submission(db, student_id="S001", name="Alice", subject="Science",
                     score=7.0, max_score=10.0):
    student = db.query(models.Student).filter_by(student_id=student_id).first()
    if not student:
        student = models.Student(student_id=student_id, name=name, class_grade="Grade 8")
        db.add(student)
        db.flush()
    sub = models.Submission(
        student_id=student_id,
        subject_name=subject,
        total_marks=score,
        max_total_marks=max_score,
        num_questions=1,
        status=models.SubmissionStatus.checked.value,
    )
    db.add(sub)
    db.flush()
    db.add(models.Answer(
        submission_id=sub.submission_id,
        question_number=1,
        question_text="What is photosynthesis?",
        answer_text="Plants make food using sunlight.",
        correct_answer_text="Photosynthesis is the process by which plants use sunlight.",
        marks_obtained=score,
        max_marks=max_score,
        similarity_score=0.75,
        ai_feedback="Good answer, but missing some key points",
    ))
    db.commit()
    db.refresh(sub)
    return sub


def _upload_key(subject, questions):
    return client.post("/api/upload-answer-key",
                       data={"subject": subject, "questions": json.dumps(questions)}, auth=AUTH)


# ── Auth ─────────────────────────────────────────────────────────────────────
def test_unauthenticated_request_returns_401():
    assert client.get("/api/status").status_code == 401


def test_wrong_password_returns_401():
    assert client.get("/api/status", auth=(TEST_USER, "nope")).status_code == 401


# ── Status ───────────────────────────────────────────────────────────────────
def test_get_status():
    data = client.get("/api/status", auth=AUTH).json()
    assert data["status"] == "running"
    assert "nlp_loaded" in data and "nlp_available" in data


# ── Subjects ─────────────────────────────────────────────────────────────────
def test_subjects_returns_defaults():
    subjects = client.get("/api/subjects", auth=AUTH).json()["subjects"]
    assert "Science" in subjects
    assert "Mathematics" in subjects


def test_subjects_includes_uploaded_subject():
    _upload_key("Physics", [{"question": "What is gravity?", "answer": "A force of attraction."}])
    assert "Physics" in client.get("/api/subjects", auth=AUTH).json()["subjects"]


# ── Answer-key upload + question-bank ────────────────────────────────────────
def test_upload_answer_key_and_list():
    resp = _upload_key("Biology", [
        {"question": "What is osmosis?", "answer": "Movement of water across a membrane."},
        {"question": "What is diffusion?", "answer": "Movement of particles high to low."},
    ])
    assert resp.status_code == 200
    assert resp.json()["added"] == 2

    entries = client.get("/api/question-bank?subject=Biology", auth=AUTH).json()
    assert len(entries) == 2
    assert {e["question"] for e in entries} == {"What is osmosis?", "What is diffusion?"}
    assert entries[0]["subject"] == "Biology"


def test_upload_answer_key_updates_duplicate():
    _upload_key("Biology", [{"question": "What is DNA?", "answer": "Deoxyribonucleic acid."}])
    _upload_key("Biology", [{"question": "What is DNA?", "answer": "Updated answer."}])
    entries = client.get("/api/question-bank?subject=Biology", auth=AUTH).json()
    dna = [e for e in entries if e["question"] == "What is DNA?"]
    assert len(dna) == 1
    assert dna[0]["answer"] == "Updated answer."


def test_upload_answer_key_invalid_json_returns_400():
    resp = client.post("/api/upload-answer-key",
                       data={"subject": "X", "questions": "not-json"}, auth=AUTH)
    assert resp.status_code == 400


def test_delete_question_bank_entry():
    _upload_key("History", [{"question": "Delete me?", "answer": "Yes."}])
    entry_id = client.get("/api/question-bank?subject=History", auth=AUTH).json()[0]["id"]
    resp = client.delete(f"/api/question-bank/{entry_id}", auth=AUTH)
    assert resp.status_code == 200
    assert resp.json()["deleted"] == entry_id
    assert client.get("/api/question-bank?subject=History", auth=AUTH).json() == []


def test_delete_nonexistent_entry_returns_404():
    assert client.delete("/api/question-bank/99999", auth=AUTH).status_code == 404


# ── Result retrieval ─────────────────────────────────────────────────────────
def test_get_result_by_id_includes_feedback():
    db = TestingSessionLocal()
    sub_id = _seed_submission(db, student_id="S003", name="Dave", score=9.0).submission_id
    db.close()

    data = client.get(f"/api/result/{sub_id}", auth=AUTH).json()
    assert data["studentName"] == "Dave"
    assert data["score"] == pytest.approx(90.0, abs=0.1)
    assert data["grade"] == "A+"
    assert len(data["questions"]) == 1
    q = data["questions"][0]
    assert q["aiFeedback"] == "Good answer, but missing some key points"
    assert q["correctAnswer"]


def test_get_result_nonexistent_returns_404():
    assert client.get("/api/result/99999", auth=AUTH).status_code == 404


# ── Stats ────────────────────────────────────────────────────────────────────
def test_stats_empty():
    data = client.get("/api/stats", auth=AUTH).json()
    assert data["totalStudents"] == 0
    assert data["totalPapers"] == 0
    assert data["averageScore"] == 0.0


def test_stats_with_data():
    db = TestingSessionLocal()
    _seed_submission(db, score=8.0, max_score=10.0)
    db.close()
    data = client.get("/api/stats", auth=AUTH).json()
    assert data["totalStudents"] == 1
    assert data["totalPapers"] == 1
    assert data["averageScore"] == pytest.approx(80.0, abs=0.1)


# ── Dashboard ────────────────────────────────────────────────────────────────
def test_dashboard_empty():
    data = client.get("/api/dashboard", auth=AUTH).json()
    assert data["recentActivity"] == []
    assert data["topPerformers"] == []
    assert data["subjectStats"] == []


def test_dashboard_with_data():
    db = TestingSessionLocal()
    _seed_submission(db)
    db.close()
    data = client.get("/api/dashboard", auth=AUTH).json()
    assert len(data["recentActivity"]) == 1
    assert data["recentActivity"][0]["name"] == "Alice"
    assert len(data["topPerformers"]) == 1
    assert len(data["subjectStats"]) == 1
    assert data["subjectStats"][0]["subject"] == "Science"


# ── Approve-answer validation ────────────────────────────────────────────────
def test_approve_answer_nonexistent_submission_returns_404():
    resp = client.post("/api/assessments/approve-answer",
                       json={"submission_id": 99999, "question_number": 1, "model_answer": "x"},
                       auth=AUTH)
    assert resp.status_code == 404


# ── Grade endpoint validation ────────────────────────────────────────────────
def test_grade_accepts_pdf(monkeypatch):
    # PDFs are now accepted (converted to an image downstream), so the content-type
    # validation must let them through to the grading pipeline.
    from backend.app import submission_service

    def _fake_process(*args, **kwargs):
        return {"ok": True}

    monkeypatch.setattr(submission_service, "process_grading_submission", _fake_process)
    resp = client.post("/api/grade",
                       files={"file": ("t.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")}, auth=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_grade_rejects_oversized_file():
    big = io.BytesIO(b"x" * (11 * 1024 * 1024))
    resp = client.post("/api/grade", files={"file": ("big.jpg", big, "image/jpeg")}, auth=AUTH,
                       headers={"content-length": str(11 * 1024 * 1024)})
    assert resp.status_code == 400
    assert "large" in resp.json()["detail"].lower()


def test_grade_rejects_invalid_file_type():
    resp = client.post("/api/grade",
                       files={"file": ("t.txt", io.BytesIO(b"hi"), "text/plain")}, auth=AUTH)
    assert resp.status_code == 400
