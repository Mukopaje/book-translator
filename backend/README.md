# Book Translator Backend - Setup Guide

## Prerequisites
- Python 3.9+
- PostgreSQL 13+
- Google Cloud Platform account with:
  - Cloud Storage enabled
  - Service account with Storage Admin role

## Setup Steps

### 1. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Set Up PostgreSQL Database
```bash
# Create database
createdb book_translator

# Or using psql:
psql -U postgres
CREATE DATABASE book_translator;
\q
```

### 3. Configure Environment Variables
```bash
# Copy example env file
cp .env.example .env

# Edit .env and fill in:
# - DATABASE_URL (PostgreSQL connection string)
# - SECRET_KEY (generate with: openssl rand -hex 32)
# - GCS bucket names
# - Google service account credentials path
# - SendGrid API key (optional, for email notifications)
```

### 4. Initialize Database
The database tables will be created automatically on first run, but you can also use Alembic:

```bash
# Generate initial migration
alembic init alembic
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

### 5. Run the Server
```bash
# Development mode with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 6. Verify Installation
Open browser to:
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## API Endpoints

### Authentication
- `POST /auth/signup` - Register new user
- `POST /auth/login` - Login and get JWT token

### Projects
- `POST /projects` - Create new project
- `GET /projects` - List user's projects
- `GET /projects/{id}` - Get project details
- `PATCH /projects/{id}` - Update project
- `DELETE /projects/{id}` - Delete project

### Pages
- `POST /projects/{id}/pages` - Upload page image
- `GET /projects/{id}/pages` - List pages
- `GET /projects/{id}/pages/{page_id}` - Get page details
- `GET /projects/{id}/pages/{page_id}/download` - Get download URL
- `DELETE /projects/{id}/pages/{page_id}` - Delete page

## Google Cloud Storage Setup

### 1. Create GCS Buckets
```bash
gsutil mb gs://book-translator-originals
gsutil mb gs://book-translator-outputs
```

### 2. Create Service Account
```bash
# Create service account
gcloud iam service-accounts create book-translator \
    --display-name="Book Translator Service"

# Grant Storage Admin role
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:book-translator@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

# Download key
gcloud iam service-accounts keys create service-account-key.json \
    --iam-account=book-translator@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### 3. Update .env
```
GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json
GCS_BUCKET_ORIGINALS=book-translator-originals
GCS_BUCKET_OUTPUTS=book-translator-outputs
```

## Testing the API

### 1. Sign up
```bash
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123","full_name":"Test User"}'
```

### 2. Login
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

### 3. Create Project
```bash
TOKEN="your_jwt_token_here"

curl -X POST http://localhost:8000/projects \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title":"4-Stroke Engine Manual",
    "author":"Unknown",
    "source_language":"ja",
    "target_language":"en",
    "book_context":"Technical manual for 4-stroke motorcycle engines"
  }'
```

### 4. Upload Page
```bash
curl -X POST http://localhost:8000/projects/1/pages \
  -H "Authorization: Bearer $TOKEN" \
  -F "page_number=1" \
  -F "file=@/path/to/page1.jpg"
```

## Next Steps
- Integrate with Streamlit frontend (see ../FRONTEND_INTEGRATION.md)
- Set up async job processing (Phase 4)
- Configure email notifications
- Deploy to cloud platform (GCP, AWS, Azure)
