"""
T1: Tests for shared backend utilities (grade boundaries, correct threshold).
"""
import os
import pytest
from backend.app.utils import get_grade, get_correct_threshold


# ── get_grade ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("score,expected", [
    (100.0, "A+"),
    (90.0,  "A+"),
    (89.9,  "A"),
    (80.0,  "A"),
    (79.9,  "B"),
    (70.0,  "B"),
    (69.9,  "C"),
    (60.0,  "C"),
    (59.9,  "D"),
    (0.0,   "D"),
])
def test_get_grade_boundaries(score, expected):
    assert get_grade(score) == expected


# ── get_correct_threshold ──────────────────────────────────────────────────────

def test_default_threshold_is_0_7(monkeypatch):
    monkeypatch.delenv("CORRECT_ANSWER_THRESHOLD", raising=False)
    assert get_correct_threshold() == pytest.approx(0.7)


def test_custom_threshold_from_env(monkeypatch):
    monkeypatch.setenv("CORRECT_ANSWER_THRESHOLD", "0.6")
    assert get_correct_threshold() == pytest.approx(0.6)


def test_invalid_threshold_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("CORRECT_ANSWER_THRESHOLD", "not_a_number")
    assert get_correct_threshold() == pytest.approx(0.7)


def test_out_of_range_threshold_falls_back(monkeypatch):
    monkeypatch.setenv("CORRECT_ANSWER_THRESHOLD", "1.5")
    assert get_correct_threshold() == pytest.approx(0.7)


def test_zero_threshold_is_valid(monkeypatch):
    monkeypatch.setenv("CORRECT_ANSWER_THRESHOLD", "0.0")
    assert get_correct_threshold() == pytest.approx(0.0)


def test_one_threshold_is_valid(monkeypatch):
    monkeypatch.setenv("CORRECT_ANSWER_THRESHOLD", "1.0")
    assert get_correct_threshold() == pytest.approx(1.0)
