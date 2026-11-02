@echo off
cd /d "%~dp0"
if not exist .venv (
  py -3.11 -m venv .venv
  .venv\Scripts\python -m pip install -r server\requirements.txt
)
start "" http://localhost:8000
.venv\Scripts\python -m uvicorn server.main:app --port 8000
pause
