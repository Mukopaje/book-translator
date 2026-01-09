# Phase 4: Async Processing Setup Guide

## Prerequisites Installed

1. **Redis Server** (required for Celery)
2. **New Python packages** (celery, redis, flower, PyPDF2)

---

## Installation Steps

### 1. Install Redis on Windows

**Option A: Using Chocolatey (Recommended)**
```powershell
choco install redis-64
redis-server --service-install
redis-server --service-start
```

**Option B: Using WSL2**
```bash
wsl --install  # If not already installed
wsl
sudo apt update
sudo apt install redis-server
sudo service redis-server start
```

**Option C: Docker**
```bash
docker run -d -p 6379:6379 --name redis redis:latest
```

### 2. Verify Redis is Running
```powershell
redis-cli ping
# Should return: PONG
```

### 3. Install Python Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 4. Update `.env` File
Add these lines to `backend/.env`:
```env
# Redis & Celery Configuration
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

---

## Running the System

You'll now run **3 processes** instead of 2:

### Terminal 1: Backend API
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### Terminal 2: Celery Worker
```bash
cd backend
celery -A app.celery_app worker --loglevel=info --pool=solo
```

**Note**: Use `--pool=solo` on Windows. On Linux/Mac, use `--pool=prefork`.

### Terminal 3: Celery Flower (Optional Monitoring)
```bash
cd backend
celery -A app.celery_app flower --port=5555
```

Visit http://localhost:5555 to see task dashboard.

### Terminal 4: Frontend
```bash
streamlit run app_v3.py
```

---

## New API Endpoints

### 1. Queue Single Page
```http
POST /tasks/projects/{project_id}/process-page/{page_id}
```

Response:
```json
{
  "task_id": "abc123...",
  "status": "queued",
  "page_id": 1,
  "page_number": 28
}
```

### 2. Queue Batch Processing
```http
POST /tasks/projects/{project_id}/process-batch
Content-Type: application/json

{
  "page_ids": [1, 2, 3, 4, 5]
}
```

Response:
```json
{
  "task_id": "def456...",
  "status": "queued",
  "total_pages": 5,
  "page_ids": [1, 2, 3, 4, 5]
}
```

### 3. Check Task Status
```http
GET /tasks/status/{task_id}
```

Response (while processing):
```json
{
  "task_id": "abc123...",
  "status": "processing",
  "current": 3,
  "total": 5
}
```

Response (completed):
```json
{
  "task_id": "abc123...",
  "status": "completed",
  "result": {
    "total": 5,
    "completed": 4,
    "failed": 1,
    "results": [...]
  }
}
```

### 4. Cancel Task
```http
POST /tasks/cancel/{task_id}
```

---

## Testing Async Processing

1. **Start all services** (Redis, Backend, Celery Worker)

2. **Upload pages via API**:
```bash
curl -X POST http://localhost:8001/projects/1/pages \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@page28.jpg" \
  -F "page_number=28"
```

3. **Queue for processing**:
```bash
curl -X POST http://localhost:8001/tasks/projects/1/process-page/1 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

4. **Check status**:
```bash
curl http://localhost:8001/tasks/status/TASK_ID
```

---

## Frontend Integration (Next Step)

Update `app_v3.py` to:
- Add "Process All Pending" button
- Call `/tasks/projects/{id}/process-batch` with all pending page IDs
- Poll `/tasks/status/{task_id}` every 3 seconds
- Show progress bar: "Processing page 3/10..."
- Auto-refresh page list when complete

---

## Troubleshooting

### Redis Connection Error
```
Error: ConnectionRefusedError: [Errno 111] Connection refused
```

**Fix**: Ensure Redis is running:
```bash
redis-cli ping  # Should return PONG
```

### Celery Worker Not Starting
```
Error: ImportError: No module named 'celery'
```

**Fix**: Install dependencies:
```bash
pip install celery redis
```

### Tasks Stuck in PENDING
```
Task status always shows "pending"
```

**Fix**: 
1. Check Celery worker is running
2. Verify Redis URL in .env matches worker connection
3. Check worker logs for errors

### Windows Pool Error
```
Error: NotImplementedError: pool is not supported on Windows
```

**Fix**: Use `--pool=solo`:
```bash
celery -A app.celery_app worker --loglevel=info --pool=solo
```

---

## Next Steps

1. ✅ Redis installed and running
2. ✅ Celery worker starting successfully  
3. ✅ Backend accepts task queue requests
4. ⏳ Update frontend to use async endpoints
5. ⏳ Add progress bar and status polling
6. ⏳ Test batch processing 10+ pages

**Current Status**: Backend infrastructure ready. Frontend updates needed.
