@echo off
setlocal enabledelayedexpansion
REM ============================================================
REM  QuizWeaver Launcher for Windows
REM  Double-click this file to start QuizWeaver.
REM ============================================================

title QuizWeaver

echo.
echo  ============================================
echo   QuizWeaver - Language-Model-Assisted
echo   Teaching Platform
echo  ============================================
echo.

REM --- Change to script directory (handles spaces in path) ---
cd /d "%~dp0"

REM --- Check Python ---
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo  [FAIL] Python is not installed or not in your PATH.
    echo.
    echo  To install Python:
    echo    1. Go to https://www.python.org/downloads/
    echo    2. Download Python 3.9 or newer
    echo    3. IMPORTANT: Check "Add Python to PATH" during installation
    echo    4. Restart your computer, then try again.
    echo.
    pause
    exit /b 1
)

REM --- Check Python version (need 3.9+) ---
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  [OK] Found Python %PYVER%

REM --- Create config.yaml if missing ---
if not exist "config.yaml" (
    echo  Creating default config.yaml...
    (
        echo paths:
        echo   database_file: quiz_warehouse.db
        echo llm:
        echo   provider: mock
        echo generation:
        echo   default_grade_level: 7th Grade
    ) > "config.yaml"
    echo  [OK] Created config.yaml with safe defaults
)

REM --- Install dependencies if needed ---
if not exist ".deps_installed" (
    echo.
    echo  Installing dependencies ^(first run only, may take a minute^)...
    echo.
    python -m pip install -r requirements.txt --quiet
    if !ERRORLEVEL! neq 0 (
        echo.
        echo  [FAIL] Could not install dependencies.
        echo  Try running: python -m pip install -r requirements.txt
        echo.
        pause
        exit /b 1
    )
    echo. > ".deps_installed"
    echo  [OK] Dependencies installed
) else (
    echo  [OK] Dependencies already installed
)

REM --- Detect port conflict ---
set PORT=5000
netstat -an 2>nul | findstr ":5000 .*LISTENING" >nul 2>nul
if !ERRORLEVEL! equ 0 (
    echo  [NOTE] Port 5000 is in use. Using port 5001 instead.
    set PORT=5001
)

echo.
echo  Starting QuizWeaver...
echo  URL: http://localhost:!PORT!
echo.
echo  To stop the server, close this window or press Ctrl+C.
echo  ============================================
echo.

REM --- Open browser after a short delay ---
set LAUNCH_URL=http://localhost:!PORT!
start "" cmd /c "timeout /t 2 /nobreak >nul && start %LAUNCH_URL%"

REM --- Start the app (with .env loading) ---
python -c "import os; from dotenv import load_dotenv; load_dotenv() if os.path.exists('.env') else None; import yaml; config = yaml.safe_load(open('config.yaml')); from src.web.app import create_app; app = create_app(config); app.run(host='127.0.0.1', port=!PORT!)"

if !ERRORLEVEL! neq 0 (
    echo.
    echo  [FAIL] QuizWeaver exited with an error.
    echo  Check the messages above for details.
    echo.
    pause
)

endlocal
