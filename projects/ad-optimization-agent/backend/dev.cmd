@echo off
cd /d "%~dp0"
rem Run this project's Python and reload only the app directory.
".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8030
