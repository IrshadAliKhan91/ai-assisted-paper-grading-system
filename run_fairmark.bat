@echo off
setlocal
cd /d "%~dp0"
title FairMark Launcher

where python >nul 2>&1 || (echo Python 3.10+ is required. Install it from python.org.& pause & exit /b 1)
where npm >nul 2>&1 || (echo Node.js LTS is required. Install it from nodejs.org.& pause & exit /b 1)

if not exist "backend\venv\Scripts\python.exe" (
    echo Creating local Python environment...
    python -m venv backend\venv || (pause & exit /b 1)
)

backend\venv\Scripts\python.exe -c "import fastapi, sqlalchemy" >nul 2>&1
if errorlevel 1 (
    echo Installing backend packages. This only happens on the first run...
    backend\venv\Scripts\python.exe -m pip install -q -r backend\requirements.txt || (echo Backend setup failed.& pause & exit /b 1)
)

if not exist "frontend\node_modules" (
    echo Installing frontend packages. This only happens on the first run...
    call npm --prefix frontend install || (echo Frontend setup failed.& pause & exit /b 1)
)

if not exist "frontend\.fairmark-build-ready" (
    echo Building the local app. This only happens on the first run...
    call npm --prefix frontend run build || (echo Frontend build failed.& pause & exit /b 1)
    type nul > "frontend\.fairmark-build-ready"
)

if not exist "backend\fairmark.db" (
    echo Preparing local database. This only happens on the first run...
    backend\venv\Scripts\python.exe backend\create_db.py || (echo Database setup failed.& pause & exit /b 1)
)

netstat -ano | findstr /r /c:":8010 .*LISTENING" >nul 2>&1 && (
    echo FairMark is already running at http://localhost:8010
    start "" http://localhost:8010
    exit /b 0
)
start "FairMark Server" /min /d "%~dp0backend" cmd /c "venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010"

echo Starting FairMark...
set attempts=0
:wait
set /a attempts+=1
curl -s -o nul -m 2 http://127.0.0.1:8010/ >nul 2>&1 && goto ready
if %attempts% GEQ 45 (echo FairMark did not start. Run this file from a Command Prompt to see errors.& pause & exit /b 1)
timeout /t 2 >nul
goto wait
:ready
start "" http://localhost:8010
exit /b 0
