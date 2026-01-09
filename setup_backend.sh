#!/bin/bash
# Quick setup script for Linux/Mac

set -e

echo "========================================"
echo "Book Translator Backend - Quick Setup"
echo "========================================"
echo ""

echo "[1/6] Checking Python installation..."
python3 --version
echo ""

echo "[2/6] Installing backend dependencies..."
cd backend
pip3 install -r requirements.txt
echo ""

echo "[3/6] Checking .env configuration..."
if [ ! -f .env ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo ""
    echo "IMPORTANT: Please edit backend/.env file with your settings:"
    echo "  - DATABASE_URL (PostgreSQL connection)"
    echo "  - SECRET_KEY (generate with: openssl rand -hex 32)"
    echo "  - Google Cloud credentials"
    echo ""
    read -p "Press Enter after editing .env..."
fi
echo ""

echo "[4/6] Checking PostgreSQL..."
echo "NOTE: Make sure PostgreSQL is running and database 'book_translator' exists"
echo "You can create it with: createdb book_translator"
echo ""
read -p "Press Enter to continue..."

echo "[5/6] Testing database connection..."
python3 -c "from app.config import settings; print(f'Database URL: {settings.database_url}')" || true
echo ""

echo "[6/6] Ready to start!"
echo ""
echo "To start the backend server, run:"
echo "  cd backend"
echo "  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "API documentation will be available at:"
echo "  http://localhost:8000/docs"
echo ""
