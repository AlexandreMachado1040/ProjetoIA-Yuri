@echo off
echo ======================================================
echo  Motor PVSyst v2.3 - Backend FastAPI
echo ======================================================
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
py -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
pause
