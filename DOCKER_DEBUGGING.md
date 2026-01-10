# Docker Debugging Guide - How to See Errors in Terminal

## Quick Commands

### Option 1: Run in Foreground (Best for seeing errors immediately)
```bash
# Start all services and see logs in terminal (Ctrl+C to stop)
docker-compose up

# Start only backend and worker (where errors occur)
docker-compose up backend worker

# Start only backend to see API errors
docker-compose up backend
```

### Option 2: View Logs from Running Containers
```bash
# Follow logs in real-time from all services (Ctrl+C to stop)
docker-compose logs -f

# Follow logs from specific service
docker-compose logs -f backend
docker-compose logs -f worker

# View last 100 lines of logs
docker-compose logs --tail=100

# View logs from specific service with timestamp
docker-compose logs -f --timestamps backend
```

### Option 3: View Logs from Individual Containers
```bash
# See logs from a specific container
docker logs book-translator-backend -f
docker logs book-translator-worker -f

# See last 50 lines with timestamps
docker logs book-translator-worker --tail=50 --timestamps
```

## Common Workflows

### 1. Starting Fresh (See All Errors)
```bash
# Stop any running containers
docker-compose down

# Start in foreground to see all errors
docker-compose up
```

### 2. Debugging a Specific Service
```bash
# Start only backend with full logging
docker-compose up backend

# In another terminal, check worker logs
docker-compose logs -f worker
```

### 3. Testing Backend API Errors
```bash
# Start backend in foreground
docker-compose up backend

# Make API calls and see errors directly in terminal
```

### 4. Testing Worker/Celery Errors
```bash
# Start worker in foreground
docker-compose up worker

# Submit a task and see errors directly
```

## Additional Debugging Tips

### See Container Status
```bash
# List running containers
docker-compose ps

# See container resource usage
docker stats
```

### Execute Commands Inside Container
```bash
# Open shell in backend container
docker-compose exec backend bash

# Open shell in worker container
docker-compose exec worker bash

# Run Python command in backend
docker-compose exec backend python -c "print('test')"
```

### Check Environment Variables
```bash
# See environment variables in container
docker-compose exec backend env

# Check if .env file is loaded
docker-compose exec backend printenv | grep -i api
```

### Restart Services and See Logs
```bash
# Restart backend and see logs
docker-compose restart backend
docker-compose logs -f backend

# Rebuild and restart (if code changed)
docker-compose up --build backend
```

## Important Notes

1. **Foreground Mode (`docker-compose up` without `-d`)**: Best for debugging - you see all errors immediately
2. **Detached Mode (`docker-compose up -d`)**: Runs in background - use `docker-compose logs -f` to see errors
3. **Log Buffering**: Some Python output may be buffered. Use `PYTHONUNBUFFERED=1` in docker-compose.yml for immediate output
4. **Error Colors**: Errors typically appear in red in terminal output

## Quick Fix: Ensure Immediate Output

Add to your `docker-compose.yml` in the environment section:
```yaml
environment:
  - PYTHONUNBUFFERED=1
```

This ensures Python prints immediately without buffering, so you see errors right away.

