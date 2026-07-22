# Architecture

FairMark uses a three-tier application design. The React client handles the teacher workflow, FastAPI coordinates extraction and grading, and PostgreSQL stores the durable academic record.

![System architecture](architecture/system_architecture_uml.png)

## Components

| Component | Responsibility |
| --- | --- |
| `frontend/` | Upload papers, manage answer keys, view results, search history, and export PDF reports. |
| `backend/app/api/` | Authenticated REST endpoints and request validation. |
| `backend/app/ocr_service.py` | Converts files to images where needed, calls OCR providers in sequence, and parses the returned text. |
| `backend/app/submission_service.py` | Matches extracted questions, calls the grader, scales marks, and writes results atomically. |
| `backend/app/nlp_grading_service.py` | Uses an LLM when configured and a local semantic/heuristic grader when it is unavailable. |
| PostgreSQL | Stores students, assessments, question-bank entries, submissions, and answer-level feedback. |

## Processing path

```text
Upload -> file validation -> OCR -> Q&A parsing -> question-bank match
       -> grading -> review flags -> database -> dashboard / PDF export
```

The OCR layer is provider-agnostic. It tries configured services in a fallback sequence, with local Tesseract as the last option. The grading layer also avoids a single point of failure: Gemini is the primary grader and the SBERT/heuristic implementation is the local fallback.

## Teacher review

Automation is assistive, not autonomous. FairMark flags low-confidence extraction and unmatched questions for review. Teachers can correct OCR output and approve answers from the application before relying on a result.

## Diagrams

- [Detailed UML system architecture](architecture/system_architecture_uml.png)

The source scripts for the diagrams are in [`scripts/`](../scripts/).
