@echo off
REM Quick setup script for Windows

echo ========================================
echo Book Translator Backend - Quick Setup
echo ========================================
echo.

echo [1/6] Checking Python installation...
python --version
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Please install Python 3.9+
    exit /b 1
)
echo.

echo [2/6] Installing backend dependencies...
cd backend
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    exit /b 1
)
echo.

echo [3/6] Checking .env configuration...
if not exist .env (
    echo Creating .env from template...
    copy .env.example .env
    echo.
    echo IMPORTANT: Please edit backend\.env file with your settings:
    echo   - DATABASE_URL (PostgreSQL connection)
    echo   - SECRET_KEY (generate with: openssl rand -hex 32)
    echo   - Google Cloud credentials
    echo.
    echo Press any key after editing .env...
    pause
)
echo.

echo [4/6] Checking PostgreSQL...
echo NOTE: Make sure PostgreSQL is running and database 'book_translator' exists
echo You can create it with: createdb book_translator
echo.
pause

echo [5/6] Testing database connection...
python -c "from app.config import settings; print(f'Database URL: {settings.database_url}')"
echo.

echo [6/6] Ready to start!
echo.
echo To start the backend server, run:
echo   cd backend
echo   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
echo.
echo API documentation will be available at:
echo   http://localhost:8000/docs
echo.

pause
