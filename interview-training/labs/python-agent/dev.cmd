@echo off
setlocal
rem Start the project Python from this script's directory.
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Project Python not found: .venv\Scripts\python.exe
    popd
    exit /b 1
)
".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8000
set "serverExitCode=%errorlevel%"
popd
exit /b %serverExitCode%
