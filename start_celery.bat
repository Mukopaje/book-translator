@echo off
REM Start Celery worker for Windows

echo Starting Celery worker...
echo Worker will process translation tasks from Redis queue
echo Press Ctrl+C to stop

cd /d "%~dp0"
cd backend

REM Activate virtual environment
call ..\venv\Scripts\activate.bat

REM Start Celery worker
celery -A app.celery_app worker --loglevel=info --pool=solo -Q translation

pause
