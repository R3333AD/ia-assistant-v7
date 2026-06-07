@echo off
taskkill /f /im pythonw.exe >nul 2>&1
echo Agent arrêté.
timeout /t 2 /nobreak >nul
