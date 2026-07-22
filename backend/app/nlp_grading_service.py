"""
NLP Grading Service for FairMark Backend
Integrates with the NLP module for semantic similarity-based grading.

Reference-answer generation uses OpenRouter free text models (same API key
as OCR). Gemini has been removed — all 1.5/2.0 flash endpoints return 404.
"""
import os
import sys
import logging
import requests
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Point to new Grading Model v2 source
_default_nlp_path = str(Path(__file__).parent.parent.parent / 'grading-model' / 'src')
NLP_SOURCE_PATH = Path(os.getenv('NLP_MODEL_PATH', _default_nlp_path))
sys.path.insert(0, str(NLP_SOURCE_PATH))

BACKEND_ENV_PATH = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=BACKEND_ENV_PATH)

def _collect_openrouter_keys():
    """OPENROUTER_API_KEY, OPENROUTER_API_KEY_2..9 → list (multi-account failover)."""
    keys = []
    primary = os.getenv('OPENROUTER_API_KEY')
    if primary:
        keys.append(primary)
    for i in range(2, 10):
        k = os.getenv(f'OPENROUTER_API_KEY_{i}')
        if k:
            keys.append(k)
    return keys

OPENROUTER_API_KEYS = _collect_openrouter_keys()
OPENROUTER_API_KEY = OPENROUTER_API_KEYS[0] if OPENROUTER_API_KEYS else ''  # back-compat

# Ordered by reliability — put the model that succeeds most often first.
# These must be real OpenRouter free-tier model IDs (gemma-4 does not exist —
# the previous list 404'd on every call, silently disabling reference generation).
_OPENROUTER_TEXT_MODELS = [
    'openai/gpt-oss-20b:free',
    'meta-llama/llama-3.3-70b-instruct:free',
    'google/gemma-2-9b-it:free',
]

_grading_model = None
_preprocess_fn = None
_llm_grader = None
_llm_unavailable = False
_llm_consecutive_failures = 0
_LLM_MAX_CONSECUTIVE_FAILURES = 5


def get_llm_grader():
    """
    Lazy-load the Gemini LLM grader — the spec-defined PRIMARY grading engine.
    Returns None (and never retries) if google-genai isn't installed or no
    GEMINI_API_KEY is configured, so the pipeline transparently falls back to
    the local heuristic engine (same design as Grading Model/src/app.py).
    """
    global _llm_grader, _llm_unavailable
    if _llm_unavailable:
        return None
    if _llm_grader is None:
        try:
            from grading_llm import LLMGrader
            grader = LLMGrader()  # reads GEMINI_API_KEY + GEMINI_API_KEY_2..9 from env
            if not grader.is_available():
                logger.info("Gemini LLM grader not configured — using local heuristic engine.")
                _llm_unavailable = True
                return None
            _llm_grader = grader
            logger.info("Gemini LLM grader loaded as primary grading engine.")
        except Exception as e:
            logger.info(f"Gemini LLM grader unavailable ({type(e).__name__}) — using local heuristic engine.")
            _llm_unavailable = True
            return None
    return _llm_grader


def _heuristic_feedback(raw_marks: float) -> str:
    """Deterministic feedback (0-10 scale) for the heuristic path — no network call."""
    if raw_marks >= 8.5:
        return "Excellent — comprehensive and accurate answer."
    if raw_marks >= 7.0:
        return "Good answer, but a few key points are missing."
    if raw_marks >= 5.0:
        return "Partial answer — review the model answer for missing concepts."
    if raw_marks >= 2.5:
        return "Weak answer — significant content gaps."
    return "Incorrect or irrelevant — review the topic and retry."

def _is_generic_question_text(question_text: str) -> bool:
    normalized = (question_text or '').strip().lower()
    if not normalized or len(normalized) < 4:
        return True
    if normalized in {'full response', 'extracted content'}:
        return True
    if normalized.startswith('question ') and normalized[9:].strip().isdigit():
        return True
    return False

def generate_reference_answer_with_ai(question_text: str) -> Optional[str]:
    if not OPENROUTER_API_KEY:
        logger.warning("OpenRouter API key missing, cannot generate reference answer.")
        return None

    if _is_generic_question_text(question_text):
        return None

    prompt = (
        "You are an expert teacher providing the expected correct answer for a test question. "
        "Provide ONLY the direct, concise answer to the following question. "
        "Do not include any pleasantries, headers, or explanation.\n\n"
        f"Question: {question_text}\n\nAnswer:"
    )

    for key_idx, api_key in enumerate(OPENROUTER_API_KEYS, 1):
        key_rate_limited = False
        for model in _OPENROUTER_TEXT_MODELS:
            try:
                # Short connect timeout (3s) + read timeout (10s) to fail fast
                # on unreachable endpoints while still allowing slow responses.
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:3000",
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 300,
                    },
                    timeout=(3.0, 10.0),
                )
                if response.status_code == 200:
                    data = response.json()
                    text = data["choices"][0]["message"]["content"].strip()
                    if text and len(text) > 1:
                        return text
                elif response.status_code == 429:
                    logger.warning(f"Reference gen rate-limited (key {key_idx}, {model}); failing over")
                    key_rate_limited = True
                    break  # this account is exhausted — try the next key
            except Exception as e:
                logger.error(f"Reference generation error (key {key_idx}, {model}): {e}")
                continue

    return None

def get_grading_model():
    global _grading_model, _preprocess_fn
    
    if _grading_model is None:
        try:
            logger.info("Loading NLP Grading Engine v2...")
            from grading_engine import GradingModel
            from preprocessing import preprocess
            
            _grading_model = GradingModel()
            _preprocess_fn = preprocess
            
            logger.info("NLP Grading Engine v2 loaded successfully!")
        except Exception as e:
            logger.error(f"Failed to load NLP Grading Engine: {e}")
            raise
    
    return _grading_model, _preprocess_fn

def is_nlp_model_available() -> bool:
    """Check if the source file for the engine exists."""
    return (NLP_SOURCE_PATH / 'grading_engine.py').exists()

def is_nlp_loaded() -> bool:
    return _grading_model is not None

def grade_with_answer(question_text: str, student_answer: str, correct_answer: str, max_marks: float = 10.0) -> Dict:
    """
    Grade a student answer against a known correct answer (key_answer).

    Engine contract (from Grading Model README):
      - Input:  question, key_answer (REQUIRED), student_answer
      - LLM returns:  {"marks": int(0-10), "feedback": str}
      - Heuristic returns: {"marks": int(0-10)}  (no feedback field)
      - key_answer is mandatory — engine cannot grade without it.

    This function maps backend field names to engine field names:
      correct_answer  →  key_answer / key  (at the engine boundary)
    """
    global _llm_unavailable, _llm_consecutive_failures

    # ── Guard: key_answer is mandatory per engine contract ──
    if not correct_answer or not correct_answer.strip():
        return {
            'question': question_text,
            'student_answer': student_answer,
            'correct_answer': '',
            'marks': 0,
            'max_marks': max_marks,
            'similarity_score': 0.0,
            'ai_feedback': None,
            'grading_method': 'manual_review_missing_answer',
            'engine': None,
            'fallback_reason': 'key_answer is required — engine cannot grade without it',
        }

    try:
        # ── 1. Primary: Gemini LLM ──
        # LLM contract: grade(question, key, student) → {"marks": int, "feedback": str} | None
        llm = get_llm_grader()
        if llm is not None:
            llm_result = llm.grade(question_text, correct_answer, student_answer)
            if llm_result is None:
                _llm_consecutive_failures += 1
                if _llm_consecutive_failures >= _LLM_MAX_CONSECUTIVE_FAILURES:
                    logger.warning(f"LLM grader failed {_llm_consecutive_failures} times — disabling for this session")
                    _llm_unavailable = True
                else:
                    logger.warning(f"LLM grader returned None ({_llm_consecutive_failures}/{_LLM_MAX_CONSECUTIVE_FAILURES})")
            if llm_result and llm_result.get('marks') is not None:
                _llm_consecutive_failures = 0  # reset on success
                raw_marks = float(llm_result['marks'])
                raw_marks = max(0.0, min(10.0, raw_marks))
                return {
                    'question': question_text,
                    'student_answer': student_answer,
                    'correct_answer': correct_answer,
                    'marks': (raw_marks / 10.0) * max_marks,
                    'max_marks': max_marks,
                    'similarity_score': raw_marks / 10.0,
                    'ai_feedback': llm_result.get('feedback', '') or _heuristic_feedback(raw_marks),
                    'grading_method': 'provided_answer',
                    'engine': 'llm',
                    'fallback_reason': None,
                }

        # ── 2. Fallback: local heuristic engine ──
        # Heuristic contract: grade_answer(student_answer, key_answer, question_text, preprocess_fn) → {"marks": int}
        # Note: engine param is named key_answer; we pass correct_answer in that slot.
        grader, preprocess_fn = get_grading_model()
        result = grader.grade_answer(
            student_answer=student_answer,
            key_answer=correct_answer,
            question_text=question_text,
            preprocess_fn=preprocess_fn,
        )

        raw_marks = float(result.get('marks', 0))
        marks = (raw_marks / 10.0) * max_marks
        score = raw_marks / 10.0

        return {
            'question': question_text,
            'student_answer': student_answer,
            'correct_answer': correct_answer,
            'marks': marks,
            'max_marks': max_marks,
            'similarity_score': score,
            'ai_feedback': _heuristic_feedback(raw_marks),
            'grading_method': 'provided_answer',
            'engine': 'heuristic',
            'fallback_reason': None
        }
    except Exception as e:
        logger.error(f"Error in grade_with_answer: {e}")
        return {
            'question': question_text,
            'student_answer': student_answer,
            'correct_answer': correct_answer,
            'marks': 0,
            'max_marks': max_marks,
            'similarity_score': 0.0,
            'ai_feedback': None,
            'grading_method': 'manual_review_grade_with_answer_error',
            'fallback_reason': f"Could not grade against the generated answer: {type(e).__name__}: {e}"
        }

def grade_with_answers_batch(items: List[Dict]) -> List[Dict]:
    """
    Batched heuristic grading against provided keys — local engine path only.

    Used when the Gemini LLM grader is NOT active. All questions that have a
    verified key are encoded in a single batched SBERT pass (engine
    grade_answers_batch) instead of one network/CPU call per question.

    items: list of {question_text, student_answer, correct_answer, max_marks}.
    Returns a list aligned with items, each shaped like grade_with_answer().
    Falls back to per-item grade_with_answer() on any failure.
    """
    results: List[Optional[Dict]] = [None] * len(items)
    engine_idx: List[int] = []
    engine_input: List[Dict] = []

    for i, it in enumerate(items):
        key = (it.get('correct_answer') or '').strip()
        student = (it.get('student_answer') or '').strip()
        mm = float(it.get('max_marks', 10.0))
        q = it.get('question_text', '')
        if not key:
            # Mirror the grade_with_answer() guard: cannot grade without a key.
            results[i] = {
                'question': q, 'student_answer': student, 'correct_answer': '',
                'marks': 0, 'max_marks': mm, 'similarity_score': 0.0,
                'ai_feedback': None, 'grading_method': 'manual_review_missing_answer',
                'engine': None,
                'fallback_reason': 'key_answer is required — engine cannot grade without it',
            }
            continue
        engine_idx.append(i)
        engine_input.append({'student_answer': student, 'key_answer': key, 'question_text': q})

    if engine_input:
        try:
            grader, _ = get_grading_model()
            batch = grader.grade_answers_batch(engine_input)
            for j, i in enumerate(engine_idx):
                raw_marks = max(0.0, min(10.0, float(batch[j].get('marks', 0))))
                mm = float(items[i].get('max_marks', 10.0))
                key = (items[i].get('correct_answer') or '').strip()
                results[i] = {
                    'question': items[i].get('question_text', ''),
                    'student_answer': (items[i].get('student_answer') or '').strip(),
                    'correct_answer': key,
                    'marks': (raw_marks / 10.0) * mm,
                    'max_marks': mm,
                    'similarity_score': raw_marks / 10.0,
                    'ai_feedback': _heuristic_feedback(raw_marks),
                    'grading_method': 'provided_answer',
                    'engine': 'heuristic',
                    'fallback_reason': None,
                }
        except Exception as e:
            logger.error(f"Batched heuristic grading failed ({e}); falling back to per-item")
            for i in engine_idx:
                it = items[i]
                results[i] = grade_with_answer(
                    it.get('question_text', ''),
                    (it.get('student_answer') or '').strip(),
                    it.get('correct_answer', ''),
                    max_marks=float(it.get('max_marks', 10.0)),
                )

    return results


def grade_answer(question_text: str, student_answer: str, max_marks: float = 10.0) -> Dict:
    """
    Fallback for when no answer is in the bank.

    AI-generated reference answers are suggestions only. They are never used to
    award marks automatically because the model cannot know the teacher's depth,
    scope, or marking scheme. The teacher must approve/edit the suggestion first;
    approve_answer() then stores it in the question bank and regrades normally.
    """
    try:
        llm = get_llm_grader()
        if llm is not None:
            llm_result = llm.grade_without_key(question_text, student_answer)
            if llm_result and llm_result.get('marks') is not None:
                raw_marks = max(0.0, min(10.0, float(llm_result['marks'])))
                return {
                    'question': question_text, 'student_answer': student_answer,
                    'correct_answer': llm_result.get('reference_answer', ''),
                    'marks': (raw_marks / 10.0) * max_marks, 'max_marks': max_marks,
                    'similarity_score': raw_marks / 10.0,
                    'ai_feedback': llm_result.get('feedback', ''),
                    'grading_method': 'gemini_without_key',
                    'fallback_reason': None,
                }
        ai_reference = generate_reference_answer_with_ai(question_text)

        return {
            'question': question_text,
            'student_answer': student_answer,
            'correct_answer': ai_reference or "(Awaiting Teacher Model Answer)",
            'marks': 0,
            'max_marks': max_marks,
            'similarity_score': 0.0,
            'ai_feedback': (
                "Draft model answer generated for teacher review. "
                "No marks awarded until it is approved."
                if ai_reference else None
            ),
            'grading_method': (
                'manual_review_suggested_answer'
                if ai_reference else 'manual_review_missing_answer'
            ),
            'fallback_reason': (
                'AI-generated answer is a teacher-review suggestion only'
                if ai_reference else 'Model answer missing from Assessment Key'
            ),
            'suggested_answer': ai_reference,
        }
    except Exception as e:
        logger.error(f"Error grading answer: {e}")
        return {
            'question': question_text,
            'student_answer': student_answer,
            'correct_answer': '(Grading error - manual review required)',
            'marks': 0,
            'max_marks': max_marks,
            'similarity_score': 0.0,
            'ai_feedback': None,
            'grading_method': 'manual_review_grading_error',
            'fallback_reason': f"Grading model error: {e}"
        }

def _grade_single(i: int, qa: Dict, ref_answers: Dict) -> tuple:
    """Grade one question — used both sequentially and inside the thread pool."""
    question = qa.get('question_text', qa.get('question', ''))
    answer = qa.get('answer_text', qa.get('answer', ''))
    max_marks = float(qa.get('max_marks', 10.0))
    q_num = qa.get('question_number', i + 1)

    model_answer = qa.get('correct_answer') or qa.get('model_answer') or qa.get('expected_answer')

    if model_answer:
        result = grade_with_answer(question, answer, model_answer, max_marks=max_marks)
    elif answer.strip():
        # No stored key: Gemini can grade from subject knowledge when configured.
        result = grade_answer(question, answer, max_marks=max_marks)
    else:
        result = {
            'question': question,
            'student_answer': answer,
            'correct_answer': "(Awaiting Teacher Model Answer)",
            'marks': 0,
            'max_marks': max_marks,
            'similarity_score': 0.0,
            'ai_feedback': None,
            'grading_method': 'manual_review_missing_answer',
            'fallback_reason': "Model answer missing from Assessment Key",
        }

    result['question_number'] = q_num
    return i, result


def grade_answers_batch(qa_pairs: List[Dict]) -> List[Dict]:
    """
    Grade all questions that already have a verified model answer.

    For questions without a model answer, an AI draft may be generated for the
    teacher, but it is returned as manual-review metadata only and never used to
    calculate marks automatically.

    Grading itself is parallelized ONLY when the Gemini LLM grader is active
    (network-bound).  When grading is heuristic/SBERT-only the loop stays
    sequential — parallelization is a no-op without the LLM grader since
    the heuristic engine is CPU-bound and already fast (<50ms per question).
    """
    import time as _time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Split into verified-key questions and missing-key questions.
    needs_ref = []  # (index, qa) - need optional AI suggestion for teacher
    has_ref = []    # (index, qa, model_answer)

    for i, qa in enumerate(qa_pairs):
        model_answer = qa.get('correct_answer') or qa.get('model_answer') or qa.get('expected_answer')
        student_answer = (qa.get('answer_text') or qa.get('answer') or '').strip()
        if model_answer:
            has_ref.append((i, qa, model_answer))
        elif student_answer:
            # Only generate a reference answer if the student actually wrote something;
            # empty answers get 0 marks regardless — no point burning an API call.
            needs_ref.append((i, qa))

    # Generate all missing reference answers in parallel
    ref_answers = {}  # index -> answer string or None
    if needs_ref:
        def _gen_ref(idx_qa):
            idx, qa = idx_qa
            q = qa.get('question_text', qa.get('question', ''))
            return idx, generate_reference_answer_with_ai(q)

        with ThreadPoolExecutor(max_workers=min(4, len(needs_ref))) as pool:
            futures = [pool.submit(_gen_ref, item) for item in needs_ref]
            for future in as_completed(futures):
                idx, ref = future.result()
                ref_answers[idx] = ref

    # Decide whether to parallelize the grading loop
    llm = get_llm_grader()
    use_parallel = llm is not None and len(qa_pairs) > 1

    results = [None] * len(qa_pairs)
    t0 = _time.time()

    if use_parallel:
        # LLM grader is active — each call is network-bound; parallelize with
        # a small pool to avoid overrunning the free Gemini tier.
        logger.info(f"Grading {len(qa_pairs)} questions in parallel (LLM engine active)")
        with ThreadPoolExecutor(max_workers=min(3, len(qa_pairs))) as pool:
            futures = {
                pool.submit(_grade_single, i, qa, ref_answers): i
                for i, qa in enumerate(qa_pairs)
            }
            for future in as_completed(futures):
                idx, result = future.result()
                results[idx] = result
    else:
        # Heuristic/SBERT-only — sequential is fine (CPU-bound, <50ms each)
        for i, qa in enumerate(qa_pairs):
            _, result = _grade_single(i, qa, ref_answers)
            results[i] = result

    elapsed = _time.time() - t0
    logger.info(f"Grading {len(qa_pairs)} questions took {elapsed:.1f}s ({'parallel/LLM' if use_parallel else 'sequential/heuristic'})")

    return results

def find_matching_question(question_text: str) -> Optional[Dict]:
    """Stubbed out because DB mapping is now handled in submission_service.py"""
    return None

def generate_feedback(question: str, student_answer: str, model_answer: str, marks: float, max_marks: float = 10.0) -> str:
    if not OPENROUTER_API_KEY:
        return "AI feedback unavailable (missing OpenRouter API key)."

    if not student_answer or not student_answer.strip():
        return "No answer provided."

    prompt = (
        "You are a supportive and concise exam grader. "
        "Review the student's answer against the correct model answer. "
        "Provide 1-2 short sentences of constructive feedback. "
        f"The student received {marks}/{max_marks} marks.\n\n"
        f"Question: {question}\n"
        f"Model Answer: {model_answer}\n"
        f"Student Answer: {student_answer}\n\n"
        "Feedback:"
    )

    for api_key in OPENROUTER_API_KEYS:
        for model in _OPENROUTER_TEXT_MODELS:
            try:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:3000",
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 150,
                    },
                    timeout=10.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"].strip()
                elif response.status_code == 429:
                    break  # account exhausted — try next key
            except Exception:
                continue

    return "Feedback could not be generated at this time."
