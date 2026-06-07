@echo off
cd /d "%~dp0"
echo Agent IA v7 — Mode Desktop
echo.
python run_desktop.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo PyQt6 pas installe ? Lance plutot :
    echo   python app.py
    pause
)
