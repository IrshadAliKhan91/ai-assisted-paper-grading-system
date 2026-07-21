"""
Shared grading utilities for FairMark backend.
Single source of truth for grade boundaries, correct-answer threshold, etc.
"""
import os


def get_grade(score: float) -> str:
    """Return letter grade for a percentage score (0–100)."""
    if score >= 90:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    return "D"


def get_correct_threshold() -> float:
    """
    G1: Return the minimum fraction of max_marks required to count an answer
    as 'correct' in the summary stats (e.g. correctAnswers count).

    Configurable via CORRECT_ANSWER_THRESHOLD env var (0.0 – 1.0).
    Defaults to 0.7 (70 %).

    Example — set in backend/.env:
        CORRECT_ANSWER_THRESHOLD=0.6
    """
    raw = os.getenv("CORRECT_ANSWER_THRESHOLD", "0.7")
    try:
        value = float(raw)
        if not (0.0 <= value <= 1.0):
            raise ValueError(f"Must be between 0.0 and 1.0, got {value}")
        return value
    except ValueError as e:
        import logging
        logging.getLogger(__name__).warning(
            f"Invalid CORRECT_ANSWER_THRESHOLD='{raw}' ({e}). Using default 0.7."
        )
        return 0.7
