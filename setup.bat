@echo off
echo.
echo  ╔══════════════════════════════════╗
echo  ║   FRIDAY AI — Setup Script       ║
echo  ╚══════════════════════════════════╝
echo.

:: Check Python
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo  [ERROR] Python not found. Install Python 3.10+ from python.org
    pause
    exit /b 1
)

echo  [1/4] Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

echo  [2/4] Installing dependencies (this takes a few minutes)...
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

echo  [3/4] Setting up environment file...
IF NOT EXIST .env (
    copy .env.example .env
    echo  [!] Created .env — PLEASE EDIT IT with your API keys before starting!
) ELSE (
    echo  [OK] .env already exists.
)

echo  [4/4] Creating data directories...
mkdir data 2>nul
mkdir logs 2>nul
mkdir data\chromadb 2>nul

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║  Setup complete!                                     ║
echo  ║                                                      ║
echo  ║  NEXT STEPS:                                        ║
echo  ║  1. Edit .env and add your GEMINI_API_KEY           ║
echo  ║  2. Run: start_friday.bat                           ║
echo  ║  3. Open: http://localhost:8765                     ║
echo  ╚══════════════════════════════════════════════════════╝
echo.
pause
