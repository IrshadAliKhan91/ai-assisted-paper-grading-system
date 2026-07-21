"""
Tests for the answer-key grading layer using GradingEngine v2.

The model-backed grading tests skip automatically when the NLP
files are not present on disk.
"""
import pytest
from unittest.mock import patch

from backend.app.nlp_grading_service import (
    grade_with_answer,
    grade_answer,
    grade_answers_batch,
    generate_feedback,
    is_nlp_model_available,
)


needs_nlp_model = pytest.mark.skipif(
    not is_nlp_model_available(),
    reason="NLP model files not present on disk",
)


# ── Deterministic feedback ────────────────────────────────────────────────────

def test_generate_feedback_calls_openrouter():
    """Verify that feedback string is generated via OpenRouter."""
    # generate_feedback short-circuits when the module-level key is empty, so
    # patch both the key and requests.post for a deterministic result.
    with patch("backend.app.nlp_grading_service.OPENROUTER_API_KEY", "test-key"), \
         patch("backend.app.nlp_grading_service.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "Great answer!"}}]
        }

        feedback = generate_feedback(
            question="What is ATP?",
            student_answer="Energy currency",
            model_answer="Adenosine triphosphate",
            marks=5,
            max_marks=5
        )
        assert feedback == "Great answer!"


def test_missing_bank_answer_returns_suggestion_without_marks():
    with patch("backend.app.nlp_grading_service.generate_reference_answer_with_ai") as mock_generate:
        mock_generate.return_value = "Photosynthesis converts light energy into chemical energy."

        result = grade_answer(
            question_text="What is photosynthesis?",
            student_answer="Plants make food using sunlight.",
            max_marks=5,
        )

        assert result["marks"] == 0
        assert result["max_marks"] == 5
        assert result["correct_answer"] == mock_generate.return_value
        assert result["grading_method"] == "manual_review_suggested_answer"
        assert result["fallback_reason"] == "AI-generated answer is a teacher-review suggestion only"


def test_batch_missing_bank_answer_returns_suggestion_without_marks():
    with patch("backend.app.nlp_grading_service.generate_reference_answer_with_ai") as mock_generate:
        mock_generate.return_value = "A force of attraction between masses."

        results = grade_answers_batch([
            {
                "question_number": 1,
                "question_text": "What is gravity?",
                "answer_text": "Gravity pulls objects together.",
                "max_marks": 10,
            }
        ])

        assert len(results) == 1
        assert results[0]["marks"] == 0
        assert results[0]["correct_answer"] == mock_generate.return_value
        assert results[0]["grading_method"] == "manual_review_suggested_answer"


# ── Model-backed grading ────────────────────────────────────────────────────────

@needs_nlp_model
def test_grade_with_answer_strong_match_scores_high_and_scales():
    # max_marks = 5
    res = grade_with_answer(
        question_text="What is the powerhouse of the cell?",
        student_answer="The mitochondria is the powerhouse of the cell.",
        correct_answer="The mitochondrion is the powerhouse of the cell, producing ATP.",
        max_marks=5,
    )
    assert res["max_marks"] == 5
    assert res["grading_method"] == "provided_answer"
    
    # Engine scales natively to max_marks
    assert float(res["marks"]) >= 3.0
    assert float(res["marks"]) <= 5.0
    
    # Check scaling logic explicitly
    assert res["similarity_score"] == res["marks"] / 5.0


@needs_nlp_model
def test_grade_with_answer_unrelated_scores_low():
    res = grade_with_answer(
        question_text="What is the SI unit of force?",
        student_answer="I like to play football on the weekend.",
        correct_answer="The SI unit of force is the newton.",
        max_marks=10,
    )
    assert float(res["marks"]) < 4.0


@needs_nlp_model
def test_grade_answers_batch_uses_model_answer():
    pairs = [
        {"question_number": 1, "question_text": "Q1",
         "answer_text": "Paris is the capital of France.",
         "correct_answer": "The capital of France is Paris.", "max_marks": 5},
        {"question_number": 2, "question_text": "Q2",
         "answer_text": "Water is made of hydrogen and oxygen.",
         "correct_answer": "Water is H2O.", "max_marks": 20},
    ]
    results = grade_answers_batch(pairs)
    assert len(results) == 2
    assert {r["question_number"] for r in results} == {1, 2}
    
    # Check max_marks threading
    q1 = next(r for r in results if r["question_number"] == 1)
    q2 = next(r for r in results if r["question_number"] == 2)
    
    assert q1["max_marks"] == 5
    assert q2["max_marks"] == 20
    assert q1["grading_method"] == "provided_answer"
    assert q2["grading_method"] == "provided_answer"
