# FairMark - Intelligent Grading Engine

This module provides FairMark's local grading logic. It uses a hybrid approach combining local NLP (spaCy/SBERT) with an optional LLM layer (Google Gemini) for high-accuracy semantic evaluation.

## Features
- **Semantic Understanding**: Handles paraphrasing, synonyms, and complex sentence structures.
- **Converse Awareness**: Correctly grades "A won" vs "B lost" relationships.
- **Directional Guard**: Strictly enforces roles in non-symmetric relations (e.g., father/son).
- **Gemini Integration**: Uses LLM-assisted grading for stronger semantic evaluation when a verified answer key is provided.

## Directory Structure
- `src/`: Core source code.
  - `app.py`: Flask web interface and API (standalone testing only).
  - `grading_engine.py`: Local heuristic grading logic.
  - `grading_llm.py`: LLM-based grading bridge.
  - `preprocessing.py`: Text cleaning and normalization.
  - `templates/`: HTML/CSS for the interface.

## Setup
1. Create a virtual environment:
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   python -m spacy download en_core_web_sm
   ```
3. Set your Gemini API Key (optional but recommended):
   ```powershell
   $env:GEMINI_API_KEY = "your_key_here"
   ```

## Running the Interface
Run the standalone testing interface with:
```powershell
python src/app.py
```

## API Contract

### Endpoint
The standalone Flask app exposes: `POST /api/engine/grade`

> **Note:** The FastAPI backend (`/api/grade`) is a different service that orchestrates OCR + grading. It calls the engine's Python classes directly (not via HTTP). The Flask endpoint is for standalone testing only.

### Input (JSON)
| Field            | Type   | Required | Description                        |
|------------------|--------|----------|------------------------------------|
| `question`       | string | No       | The question text                  |
| `key_answer`     | string | **Yes**  | The correct/model answer           |
| `student_answer` | string | **Yes**  | The student's answer to grade      |
| `api_key`        | string | No       | Override Gemini key for this call   |

`key_answer` is **mandatory**. The engine grades against a known answer; it does not generate answers. Answer/key generation is the responsibility of the calling orchestration layer.

### Output (JSON)
| Field            | Type   | Always present | Description                              |
|------------------|--------|----------------|------------------------------------------|
| `marks`          | int    | Yes            | Score out of 10                          |
| `max_marks`      | int    | Yes            | Always 10                                |
| `feedback`       | string | Yes            | LLM feedback or empty string             |
| `engine`         | string | Yes            | `"llm"` or `"heuristic"`                |
| `question`       | string | Yes            | Echo of input                            |
| `student_answer` | string | Yes            | Echo of input                            |
| `key_answer`     | string | Yes            | Echo of input                            |

### Engine internals (for Python callers)
When calling the classes directly (as the FastAPI backend does):

- **`LLMGrader.grade(question, key, student)`** returns `{"marks": int, "feedback": str}` or `None`
- **`GradingModel.grade_answer(student_answer, key_answer, question_text, preprocess_fn)`** returns `{"marks": int}` (no feedback field)

The heuristic engine does not return feedback. Feedback for heuristic results is generated orchestration-side.

### No batch endpoint
There is no batch grading endpoint. The FastAPI backend's batch grading is a fan-out of individual `GradingModel.grade_answer()` / `LLMGrader.grade()` calls, not a single batch call to this engine.
