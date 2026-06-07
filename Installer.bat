@echo off
title Installation Agent IA v5
cd /d "%~dp0"
echo Installation des dépendances...
pip install -r requirements.txt
echo.
echo Installation terminée !
echo Lance LancerAgent.bat pour démarrer.
pause
