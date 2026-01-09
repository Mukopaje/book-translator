"""Helper script to start Celery worker on Windows."""
import subprocess
import sys
from pathlib import Path

def start_worker():
    """Start Celery worker with Windows-compatible settings."""
    backend_dir = Path(__file__).parent / "backend"
    
    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A", "app.celery_app",
        "worker",
        "--loglevel=info",
        "--pool=solo",  # Windows-compatible pool
        "-Q", "translation",
        "--concurrency=1"
    ]
    
    print("🚀 Starting Celery worker...")
    print(f"📁 Working directory: {backend_dir}")
    print(f"🔧 Command: {' '.join(cmd)}")
    print("=" * 60)
    
    try:
        subprocess.run(cmd, cwd=backend_dir)
    except KeyboardInterrupt:
        print("\n⏹️  Celery worker stopped")

if __name__ == "__main__":
    start_worker()
