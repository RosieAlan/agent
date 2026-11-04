@echo off
setlocal
rem Start the project Python from this script's directory.
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Project Python not found: .venv\Scripts\python.exe
    popd
    exit /b 1
)
".venv\Scripts\python.exe" -u scripts\dev_server.py
set "serverExitCode=%errorlevel%"
popd
exit /b %serverExitCode%
