"""
FairMark — Web Testing Interface
A local Flask app for interactive grading without CSV files.
"""

import sys
import os
import json

# Ensure src/ is on the path
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from flask import Flask, render_template, request, jsonify
from grading_engine import GradingModel
from grading_llm import LLMGrader
from preprocessing import preprocess

app = Flask(__name__)

# Lazy-load the models
_grader = None
_llm_grader = None

def get_grader():
    global _grader
    if _grader is None:
        _grader = GradingModel()
    return _grader

def get_llm_grader(api_key=None):
    global _llm_grader
    if api_key:
        return LLMGrader(api_keys=[api_key])
    if _llm_grader is None:
        _llm_grader = LLMGrader()
    return _llm_grader


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/engine/grade", methods=["POST"])
def grade_single():
    """
    Grade a single student answer.

    Contract (matches README):
      Input:  {"question": str, "key_answer": str (REQUIRED), "student_answer": str (REQUIRED)}
      Output: {"marks": int, "max_marks": 10, "feedback": str, "engine": str, ...}

    key_answer is mandatory — the engine grades against a known answer;
    it does NOT generate answers. Answer generation is orchestration-side.
    """
    data = request.get_json(force=True)
    question = data.get("question", "").strip()
    student_answer = data.get("student_answer", "").strip()
    key_answer = data.get("key_answer", "").strip()
    api_key = data.get("api_key", "").strip()

    if not student_answer or not key_answer:
        return jsonify({"error": "Both student_answer and key_answer are required."}), 400

    # 1. Primary Engine: LLM (Gemini)
    llm = get_llm_grader(api_key)
    if llm.is_available():
        result = llm.grade(question, key_answer, student_answer)
        if result and result.get("marks") is not None:
            return jsonify({
                "marks": result["marks"],
                "max_marks": 10,
                "question": question,
                "student_answer": student_answer,
                "key_answer": key_answer,
                "feedback": result.get("feedback", ""),
                "engine": "llm",
            })

    # 2. Fallback Engine: Local Heuristics
    # grading_engine returns {"marks": int} — no feedback field.
    grader = get_grader()
    result = grader.grade_answer(
        student_answer=student_answer,
        key_answer=key_answer,
        question_text=question if question else "N/A",
        preprocess_fn=preprocess,
    )

    return jsonify({
        "marks": result["marks"],
        "max_marks": 10,
        "question": question,
        "student_answer": student_answer,
        "key_answer": key_answer,
        "feedback": "",
        "engine": "heuristic",
    })


if __name__ == "__main__":
    import threading
    import webbrowser
    import time

    print("\n  FairMark — Web Interface")
    print("  -----------------------")
    print("  Starting server... (loading AI models, please wait)\n")
    get_grader()  # Pre-load
    
    def open_browser():
        time.sleep(1)
        webbrowser.open_new("http://127.0.0.1:5000")
        
    threading.Thread(target=open_browser).start()
    print("\n  * Ready! Opening browser to: http://127.0.0.1:5000\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
