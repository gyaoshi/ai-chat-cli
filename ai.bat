@echo off
rem AI Chat CLI launcher (portable)
rem Interpreter lookup order:
rem   1) AI_CHAT_CLI_PYTHON environment variable
rem   2) .venv\Scripts\python.exe in this folder
rem   3) python_path.txt in this folder (first line = python.exe path)
rem   4) python on PATH
chcp 65001 >nul
setlocal
set "PY=%AI_CHAT_CLI_PYTHON%"
if not defined PY if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "%~dp0python_path.txt" set /p PY=<"%~dp0python_path.txt"
if not defined PY set "PY=python"
"%PY%" "%~dp0main.py" %*
exit /b %errorlevel%
