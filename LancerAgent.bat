@echo off
title Agent IA v7
cd /d "%~dp0"

netstat -ano | findstr ":8501" >nul 2>&1
if %errorlevel% == 0 (
    start "" "http://localhost:8501"
    exit
)

start /b pythonw app.py >nul 2>&1
timeout /t 4 /nobreak >nul
start "" "http://localhost:8501"
