@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m uvicorn main:app --reload --reload-dir . --host 127.0.0.1 --port 8010
