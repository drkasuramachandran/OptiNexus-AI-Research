
@echo off
title OptiNexus AI - Full Application Launcher
color 0A

echo ============================================
echo          OPTINEXUS AI
echo       FULL APPLICATION LAUNCHER
echo ============================================
echo.

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"

:: Check project folders
if not exist "%BACKEND%\server.py" (
    echo ERROR: Backend server.py not found.
    pause
    exit /b 1
)

if not exist "%FRONTEND%\package.json" (
    echo ERROR: Frontend package.json not found.
    pause
    exit /b 1
)

:: Check Python environment
if not exist "%BACKEND%\.venv\Scripts\activate.bat" (
    echo ERROR: Backend virtual environment not found.
    pause
    exit /b 1
)

:: Check frontend dependencies
if not exist "%FRONTEND%\node_modules" (
    echo Frontend dependencies missing.
    echo Installing npm packages...
    cd /d "%FRONTEND%"
    call npm install
    if errorlevel 1 (
        echo ERROR: npm install failed.
        pause
        exit /b 1
    )
)

echo Starting FastAPI backend...
start "OptiNexus Backend" cmd /k "cd /d "%BACKEND%" && call .venv\Scripts\activate.bat && python -m uvicorn server:app --reload --host 127.0.0.1 --port 8000"

echo Waiting for backend...
timeout /t 5 /nobreak >nul

echo Starting React frontend...
start "OptiNexus Frontend" cmd /k "cd /d "%FRONTEND%" && npm run dev -- --host 127.0.0.1"

echo Waiting for frontend...
timeout /t 8 /nobreak >nul

echo Opening OptiNexus AI...
start "" http://localhost:5173

echo.
echo ============================================
echo       OPTINEXUS AI LAUNCH COMPLETE
echo ============================================
echo Backend:  http://127.0.0.1:8000
echo API Docs: http://127.0.0.1:8000/docs
echo Frontend: http://localhost:5173
echo.
echo Keep both server windows open.
echo Close them to stop the application.
echo ============================================
pause
