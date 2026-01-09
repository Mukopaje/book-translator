# Phase 4: Async Processing Setup

## Redis Installation for Windows

### Option 1: Memurai (Recommended for Windows)
```powershell
# Download from https://www.memurai.com/get-memurai
# Or use chocolatey:
choco install memurai
```

### Option 2: Docker Redis (Easiest)
```powershell
# Install Docker Desktop from https://www.docker.com/products/docker-desktop
# Then run:
docker run -d -p 6379:6379 --name redis redis:latest
```

### Option 3: WSL2 Redis
```powershell
# If you have WSL2 installed:
wsl
sudo apt-get update
sudo apt-get install redis-server
redis-server --daemonize yes
```

### Option 4: Cloud Redis (No local setup)
Use Redis Labs free tier: https://redis.com/try-free/
- Get connection string like: `redis://username:password@host:port`
- Add to backend/.env: `REDIS_URL=your-connection-string`

## Testing Redis Connection

```python
import redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)
r.ping()  # Should return True
```

## Starting Services

### 1. Start Redis
```powershell
# If using Memurai:
net start Memurai

# If using Docker:
docker start redis

# If using WSL:
wsl redis-server
```

### 2. Start Celery Worker
```powershell
cd backend
celery -A app.tasks.celery_app worker --loglevel=info --pool=solo
```

### 3. Start Flower (Monitoring Dashboard)
```powershell
cd backend
celery -A app.tasks.celery_app flower --port=5555
# Open http://localhost:5555 to see task status
```

### 4. Start Backend
```powershell
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### 5. Start Frontend
```powershell
streamlit run app_v3.py
```

## Environment Variables

Add to `backend/.env`:
```env
# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Email (SendGrid)
SENDGRID_API_KEY=your_key_here
FROM_EMAIL=noreply@yourdomain.com
```

## Verification

1. Check Redis: `redis-cli ping` → should return PONG
2. Check Celery: Visit http://localhost:5555 (Flower dashboard)
3. Check Backend: Visit http://localhost:8001/docs
4. Check Frontend: Visit http://localhost:8501

## Troubleshooting

**Celery won't start on Windows:**
- Use `--pool=solo` or `--pool=gevent` flag
- Install gevent: `pip install gevent`

**Redis connection refused:**
- Check if Redis is running: `redis-cli ping`
- Check firewall settings
- Try connecting to 127.0.0.1 instead of localhost

**Tasks not executing:**
- Ensure Celery worker is running
- Check Flower dashboard for errors
- Look at backend logs for task submission
