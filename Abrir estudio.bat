@echo off
cd /d "%~dp0"
if not exist .venv (
  py -3.11 -m venv .venv
  .venv\Scripts\python -m pip install -r server\requirements.txt
)
.venv\Scripts\python tools\arrancar.py
pause
