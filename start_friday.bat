@echo off
title FRIDAY AI — Always Online
echo  Starting FRIDAY...
call venv\Scripts\activate.bat 2>nul || (
    echo  [ERROR] Run setup.bat first!
    pause & exit /b 1
)
python friday.py
pause
