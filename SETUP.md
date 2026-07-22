# FairMark setup guide

This guide covers manual local setup. For the fastest Windows setup, use `run_fairmark.bat` after creating the environment files described below.

## Prerequisites

- Python 3.10 or newer
- Node.js 18 or newer
- PostgreSQL 14 or newer for the full application
- An OCR provider API key, or a local Tesseract installation

## 1. Clone and configure

```powershell
git clone https://github.com/IrshadAliKhan91/ai-assisted-paper-grading-system.git
cd ai-assisted-paper-grading-system
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
```

Edit both `.env` files before starting. At minimum, set a secure `ADMIN_PASSWORD` in `backend/.env` and use the same value for `REACT_APP_API_PASS` in `frontend/.env`. Configure `DATABASE_URL` for PostgreSQL and add at least one OCR provider credential for answer-sheet extraction.

## 2. Set up the backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
cd ..
python backend/create_db.py
```

`create_db.py` creates the configured database when required, applies Alembic migrations, and adds starter data.

Start the API from the `backend` directory:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000/api` and interactive documentation is available at `http://127.0.0.1:8000/docs`.

## 3. Set up the frontend

Open a second terminal at the repository root:

```powershell
cd frontend
npm ci
npm start
```

Open `http://localhost:3000`. The React application expects the API to be available at the URL set by `REACT_APP_API_URL`.

## 4. Optional local grading-engine interface

The core local semantic grader can also be exercised independently:

```powershell
cd grading-model
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python src/app.py
```

This standalone interface is for development and testing. The main FairMark application imports the grading engine directly rather than calling this interface over HTTP.

## Troubleshooting

- **Database connection error:** confirm PostgreSQL is running and `DATABASE_URL` in `backend/.env` is correct.
- **Authentication error:** ensure `ADMIN_USER` and `ADMIN_PASSWORD` match the frontend `REACT_APP_API_USER` and `REACT_APP_API_PASS` values.
- **OCR unavailable:** provide at least one valid provider key, or install and configure Tesseract locally.
- **Port conflict:** free port `8000` for the API or `3000` for the frontend, then restart the affected service.

Never commit `.env` files, API keys, answer sheets, or exported grading records.
