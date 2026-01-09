@echo off
echo Starting Book Translator System...

REM Start Backend API
echo Starting Backend API...
start "Backend API" cmd /k "call venv\Scripts\activate.bat && cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8001"

REM Start Celery Worker
echo Starting Celery Worker...
start "Celery Worker" cmd /k "call venv\Scripts\activate.bat && cd backend && celery -A app.celery_app worker --pool=solo -Q translation --loglevel=info"

REM Start Frontend
echo Starting Frontend...
start "Frontend" cmd /k "call venv\Scripts\activate.bat && streamlit run app_v3.py"

echo.
echo ===================================================
echo All services are starting in separate windows.
echo.
echo Backend API: http://localhost:8001/docs
echo Frontend:    http://localhost:8501
echo.
echo Keep these windows open while using the application.
echo ===================================================
pause
