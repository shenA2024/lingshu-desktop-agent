@echo off
chcp 65001 >nul
setlocal
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" -X utf8 "%~dp0doctor.py"
) else (
  python -X utf8 "%~dp0doctor.py"
)
pause
