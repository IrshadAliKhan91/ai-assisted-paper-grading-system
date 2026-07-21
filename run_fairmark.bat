@echo off
setlocal enabledelayedexpansion

:: Run from the script's own directory
cd /d "%~dp0"

echo ========================================================
echo        FairMark - Setup and Runner
echo ========================================================
echo.

:: ---------------------------------------------------------
:: 0. Prerequisite checks
:: ---------------------------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)
call npm --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm is not installed or not in PATH.
    pause
    exit /b 1
)

:: ---------------------------------------------------------
:: 1. Validate environment files (fail fast with clear guidance)
:: ---------------------------------------------------------
if not exist "backend\.env" (
    echo [ERROR] backend\.env is missing. Create it with DATABASE_URL and
    echo         ADMIN_PASSWORD ^(see SETUP.md^), then run this again.
    pause
    exit /b 1
)
findstr /B /C:"ADMIN_PASSWORD=" "backend\.env" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] ADMIN_PASSWORD is not set in backend\.env.
    echo         The backend refuses to start without it ^(see SETUP.md^).
    pause
    exit /b 1
)
if not exist "frontend\.env" (
    echo [WARN] frontend\.env is missing - API calls will return 401.
    echo        Add REACT_APP_API_USER and REACT_APP_API_PASS ^(see SETUP.md^).
    echo.
)

:: ---------------------------------------------------------
:: 2. Stop any servers already running on :8000 / :3000
::    (prevents the duplicate / stale-instance problem)
:: ---------------------------------------------------------
echo Stopping any existing servers on ports 8000 and 3000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":8000"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":3000"') do taskkill /F /PID %%a >nul 2>&1
:: brief pause so the OS releases the sockets before we rebind
timeout /t 2 >nul

:: warn if :8000 is STILL occupied (e.g. a process started as Administrator)
netstat -ano | findstr "LISTENING" | findstr ":8000" >nul 2>&1
if not errorlevel 1 (
    echo [WARN] Something is still listening on :8000 and could not be stopped.
    echo        If it was started as Administrator, close that window manually
    echo        or re-run this script as Administrator.
    echo.
)

:: ---------------------------------------------------------
:: 3. Backend environment + dependencies
:: ---------------------------------------------------------
echo [1/4] Backend environment...
cd backend
if not exist venv (
    echo Creating Python virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        cd ..
        pause
        exit /b 1
    )
)
call venv\Scripts\activate.bat
echo Installing/updating backend requirements...
python -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install backend requirements.
    cd ..
    pause
    exit /b 1
)

:: ---------------------------------------------------------
:: 4. Database setup (idempotent: create DB, apply migrations, seed)
:: ---------------------------------------------------------
echo [2/4] Database setup ^(creates DB, applies migrations, seeds^)...
python create_db.py
cd ..
echo.

:: ---------------------------------------------------------
:: 5. Frontend dependencies (only when missing)
:: ---------------------------------------------------------
echo [3/4] Frontend dependencies...
cd frontend
if not exist node_modules (
    echo Installing node modules ^(first run, may take a few minutes^)...
    call npm install
    if errorlevel 1 (
        echo [ERROR] Failed to install frontend dependencies.
        cd ..
        pause
        exit /b 1
    )
) else (
    echo node_modules already present - skipping npm install.
    echo ^(Delete node_modules to force a reinstall.^)
)
cd ..
echo.

:: ---------------------------------------------------------
:: 6. Start both servers in their own windows
::    --reload  : auto-applies code edits
::    127.0.0.1 : local only (change to 0.0.0.0 to test from another device)
:: ---------------------------------------------------------
echo [4/4] Starting servers...
echo Starting Backend  (FastAPI) on http://127.0.0.1:8000 ...
start "FairMark Backend" cmd /k "cd backend && call venv\Scripts\activate.bat && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

echo Starting Frontend (React)   on http://localhost:3000 ...
start "FairMark Frontend" cmd /k "cd frontend && npm start"

:: ---------------------------------------------------------
:: 7. Wait for the backend to become reachable
::    (it pre-loads the NLP model on startup, so give it time)
:: ---------------------------------------------------------
echo.
echo Waiting for the backend to be ready (it loads the NLP model, ~20-40s)...
set /a TRIES=0
:waitbackend
set /a TRIES+=1
curl -s -o nul -m 2 http://127.0.0.1:8000/ >nul 2>&1
if not errorlevel 1 goto backendready
if %TRIES% GEQ 40 goto backenddown
timeout /t 2 >nul
goto waitbackend

:backendready
echo [OK] Backend is responding on http://127.0.0.1:8000
goto done

:backenddown
echo [WARN] Backend did not respond in time. Check the "FairMark Backend"
echo        window for errors (e.g. PostgreSQL not running, missing keys).

:done
echo.
echo ========================================================
echo Servers launched in separate windows.
echo   Frontend : http://localhost:3000
echo   Backend  : http://127.0.0.1:8000
echo.
echo OCR needs at least one working provider. If grading fails with
echo "All OCR providers...", add keys in backend\.env or install Tesseract
echo (winget install UB-Mannheim.TesseractOCR) for an offline fallback.
echo ========================================================
pause
