# FairMark OCR Module

AI-powered OCR for extracting structured Q&A data from exam papers.

## Features

- **OpenRouter Vision Models** (Primary): Uses Molmo AI for intelligent text extraction
- **RapidAPI Fallback**: Pen-to-Print and OCR-Extract as backup options
- **Structured JSON Output**: Returns student info + Q&A pairs ready for grading

## Output Format

```json
{
  "success": true,
  "student_name": "John Doe",
  "student_id": "STU2024001",
  "subject": "English Grammar",
  "qa_pairs": [
    {
      "question_number": 1,
      "question": "What is a noun?",
      "answer": "A noun is a word that represents a person, place, thing, or idea."
    }
  ],
  "raw_text": "...",
  "model": "Molmo-Vision",
  "platform": "OpenRouter"
}
```

## Usage

### In Python

```python
from backend.app.ocr_service import extract_text, extract_text_from_bytes

# From file path
result = extract_text("exam_paper.png")

# From bytes (web uploads)
result = extract_text_from_bytes(file_bytes, "paper.png")

if result['success']:
    for qa in result['qa_pairs']:
        print(f"Q{qa['question_number']}: {qa['question']}")
        print(f"Answer: {qa['answer']}")
```

### CLI

```bash
python ocr_service.py path/to/exam_paper.png
```

## Configuration

Create `.env` files in the model directories:

**openrouter_models/.env**
```
OPENROUTER_API_KEY=your_openrouter_key
```

**rapidapi_models/.env**
```
PEN_TO_PRINT_API_KEY=your_key
OCR_EXTRACT_API_KEY=your_key
OCR_DOCUMENT_PRO_API_KEY=your_key
```

## Files

| File | Description |
|------|-------------|
| `ocr_service.py` | Main OCR service with structured extraction |
| `openrouter_models/` | OpenRouter vision model implementations |
| `rapidapi_models/` | RapidAPI OCR implementations |
| `requirements.txt` | Python dependencies |

## Integration

The backend (`backend/app/ocr_service.py`) uses this module to:
1. Extract Q&A pairs from uploaded exam papers
2. Send structured JSON to the NLP grading service
3. Return results to the frontend for display
