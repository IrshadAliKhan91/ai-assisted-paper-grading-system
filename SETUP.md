# FairMark setup guide

## Quick local demo (Windows)

1. Copy `backend/.env.example` to `backend/.env` and add your `GEMINI_API_KEY` and a secure `ADMIN_PASSWORD`.
2. Copy `frontend/.env.example` to `frontend/.env`, set the same API credentials, and set `REACT_APP_API_URL=http://localhost:8010/api`.
3. Double-click `run_fairmark.bat`.

The launcher creates the local Python environment, installs dependencies, builds the React app when needed, creates a SQLite database, and opens FairMark at `http://localhost:8010`. It does not use port 8000.

## Manual development setup

Install Python 3.10+ and Node.js 18+. Create the backend environment, install dependencies, then run the API:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python create_db.py
uvicorn app.main:app --host 127.0.0.1 --port 8010
```

In another terminal, run the React development server:

```powershell
cd frontend
npm install
npm start
```

## Configuration notes

- Use `GEMINI_API_KEY` in `backend/.env` to enable AI grading for answers without a supplied key.
- Answer keys are saved under instructor-defined key titles and new questions are scored out of 10.
- Never commit `.env` files, local databases, uploaded papers, API keys, virtual environments, or `node_modules`.
