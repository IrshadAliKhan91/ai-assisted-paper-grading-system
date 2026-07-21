"""
T1: Tests for OCR text parsing functions.
These test the regex/JSON parsing logic in ocr_service.py without
making any real API calls.
"""
import pytest
from backend.app.ocr_service import parse_student_info, parse_question_answers


# ── parse_student_info ─────────────────────────────────────────────────────────

def test_parse_student_name_standard():
    text = "Student Name: John Smith\nSubject: Science"
    info = parse_student_info(text)
    assert info["student_name"] == "John Smith"


def test_parse_student_id_roll_number():
    text = "Roll No: 2021-CS-45\nName: Alice"
    info = parse_student_info(text)
    assert info["student_id"] == "2021-CS-45"


def test_parse_student_id_registration():
    text = "Registration No: REG-001\nName: Bob"
    info = parse_student_info(text)
    assert info["student_id"] == "REG-001"


def test_parse_subject():
    text = "Subject: Computer Science\nStudent ID: S001"
    info = parse_student_info(text)
    assert info["subject"] == "Computer Science"


def test_parse_missing_fields_returns_none():
    text = "Some random text with no structured info"
    info = parse_student_info(text)
    assert info["student_name"] is None
    assert info["student_id"] is None
    assert info["subject"] is None


def test_parse_all_fields_together():
    text = (
        "STUDENT NAME: Jane Doe\n"
        "STUDENT ID: STU-2024-99\n"
        "SUBJECT: Mathematics\n"
    )
    info = parse_student_info(text)
    assert info["student_name"] == "Jane Doe"
    assert info["student_id"] == "STU-2024-99"
    assert info["subject"] == "Mathematics"


# ── parse_question_answers ─────────────────────────────────────────────────────

def test_parse_q_format():
    text = "Q1: The mitochondria is the powerhouse of the cell.\nQ2: Water is H2O."
    pairs = parse_question_answers(text)
    assert len(pairs) == 2
    assert pairs[0]["question_number"] == 1
    assert "mitochondria" in pairs[0]["answer_text"].lower()
    assert pairs[1]["question_number"] == 2


def test_parse_question_format():
    text = "Question 1: Photosynthesis converts light to energy.\nQuestion 2: DNA carries genetic info."
    pairs = parse_question_answers(text)
    assert len(pairs) == 2
    assert pairs[0]["question_number"] == 1
    assert pairs[1]["question_number"] == 2


def test_parse_question_with_question_text_embedded():
    """When OCR captures both question and answer in one block."""
    text = "Q1: What is gravity? It is the force of attraction between masses."
    pairs = parse_question_answers(text)
    assert len(pairs) == 1
    assert "gravity" in pairs[0]["question_text"].lower()
    assert "force" in pairs[0]["answer_text"].lower()


def test_parse_empty_text_returns_empty():
    pairs = parse_question_answers("")
    assert pairs == []


def test_parse_no_qa_pattern_returns_full_response():
    """Text with no Q/A markers should be treated as a single full response."""
    text = "This is a long answer with no question markers at all."
    pairs = parse_question_answers(text)
    assert len(pairs) == 1
    assert pairs[0]["question_number"] == 1
    assert pairs[0]["question_text"] == "Full Response"
    assert "long answer" in pairs[0]["answer_text"]


def test_parse_multiple_questions_correct_numbering():
    text = "Q1: First answer.\nQ2: Second answer.\nQ3: Third answer."
    pairs = parse_question_answers(text)
    numbers = [p["question_number"] for p in pairs]
    assert numbers == [1, 2, 3]


def test_parse_answer_text_not_empty():
    text = "Q1: Some meaningful answer here."
    pairs = parse_question_answers(text)
    assert len(pairs) == 1
    assert pairs[0]["answer_text"].strip() != ""


def test_parse_question_answer_blocks_explicit_markers():
    text = (
        "Q1: What is pitch?\n"
        "A1: Pitch is frequency.\n"
        "Q2: What is sound?\n"
        "Ans: Sound is a wave."
    )
    pairs = parse_question_answers(text)
    assert len(pairs) == 2
    assert pairs[0]["question_number"] == 1
    assert pairs[0]["question_text"] == "What is pitch?"
    assert pairs[0]["answer_text"] == "Pitch is frequency."
    assert pairs[1]["question_number"] == 2
    assert pairs[1]["question_text"] == "What is sound?"
    assert pairs[1]["answer_text"] == "Sound is a wave."


def test_salvage_qa_from_malformed_json():
    from backend.app.ocr_service import salvage_qa_from_malformed_json
    text = '{ "qa_pairs": [ { "question_number": 2, "question": "What is meant by \\"pitch\\" of sound ? On what factor does it depend?", }'
    pairs = salvage_qa_from_malformed_json(text)
    assert len(pairs) == 1
    assert pairs[0]["question_number"] == 2
    assert pairs[0]["question_text"] == 'What is meant by "pitch" of sound ? On what factor does it depend?'
    assert pairs[0]["answer_text"] == ""


def test_extract_text_salvage_truncated_json(monkeypatch):
    from backend.app.ocr_service import extract_text, ocr_service
    
    # Mock extract_text_from_bytes to return our malformed JSON text
    malformed_json = (
        '{ "student_name": "Alice Smith", "student_id": "STU123", "subject": "Physics", '
        '"qa_pairs": [ { "question_number": 2, "question": "What is meant by pitch of sound ? On what factor does it depend?", }'
    )
    monkeypatch.setattr(ocr_service, "extract_text_from_bytes", lambda file_bytes, filename: {
        "success": True,
        "text": malformed_json,
        "model": "mock-model",
        "platform": "OpenRouter"
    })
    
    result = extract_text(b"mock_bytes", "paper.png")
    assert result["success"] is True
    assert result["student_name"] == "Alice Smith"
    assert result["student_id"] == "STU123"
    assert result["subject"] == "Physics"
    assert len(result["questions"]) == 1
    assert result["questions"][0]["question_number"] == 2
    assert result["questions"][0]["question_text"] == "What is meant by pitch of sound ? On what factor does it depend?"
    assert result["questions"][0]["answer_text"] == ""

