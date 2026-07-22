# API overview

All API routes are prefixed with `/api` by default and use HTTP Basic authentication. Configure `ADMIN_USER` and `ADMIN_PASSWORD` in `backend/.env`; the React app sends the matching credentials from its local `.env` file.

The interactive FastAPI documentation is available at `http://127.0.0.1:8000/docs` after the backend starts.

## Main endpoints

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/status` | Health and service status. |
| POST | `/grade` | Upload and grade an answer sheet. |
| GET | `/result/{id}` | Retrieve one graded submission. |
| GET | `/history` | Browse graded submissions. |
| GET | `/search` | Search student records. |
| GET | `/stats` | Retrieve aggregate grading statistics. |
| GET | `/subjects` | List subjects with answer-key data. |
| POST | `/upload-answer-key` | Save teacher-entered answer-key content. |
| POST | `/assessments/approve-answer` | Approve a reviewed answer. |
| POST | `/answers/correct-ocr` | Correct extracted OCR text. |
| GET/PATCH/DELETE | `/question-bank` | Read and manage reusable model-answer entries. |
| GET | `/dashboard` | Dashboard summary data. |

## Typical grading request

`POST /api/grade` accepts a supported paper file and metadata required by the endpoint. The backend validates its size and signature before extraction. The response contains the saved submission, score, grade, per-answer feedback, and any review indicators.

Use the generated OpenAPI documentation for exact parameters and response schemas; it stays synchronized with the implementation in [`backend/app/api/endpoints.py`](../backend/app/api/endpoints.py).

## Error handling

- `401 Unauthorized`: frontend credentials are missing or do not match the backend configuration.
- `413` or validation error: uploaded file exceeds the limit or has an unsupported/invalid signature.
- OCR-related error: no configured provider successfully extracted the sheet; add a provider key or configure Tesseract.
- `429 Too Many Requests`: rate limiting is active for the route; retry after the supplied interval.
