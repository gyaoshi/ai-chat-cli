@echo off
rem Login window launcher (portable). Keeps the browser open so you can log in
rem at your own pace. See ai.bat for how the Python interpreter is located.
chcp 65001 >nul
setlocal
set "PY=%AI_CHAT_CLI_PYTHON%"
if not defined PY if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "%~dp0python_path.txt" set /p PY=<"%~dp0python_path.txt"
if not defined PY set "PY=python"
"%PY%" "%~dp0login_keep.py" %*
echo.
pause
exit /b %errorlevel%
