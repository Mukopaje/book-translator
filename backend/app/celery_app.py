"""Celery application for async task processing."""
from celery import Celery
from app.config import settings

# Create Celery app
celery_app = Celery(
    "book_translator",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=['app.tasks.translation']
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3300,  # 55 minutes soft limit
    worker_prefetch_multiplier=1,  # Process one task at a time
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks
)

# Task routes - Using default 'celery' queue for all tasks
# celery_app.conf.task_routes = {
#     'app.tasks.translation.process_page_task': {'queue': 'translation'},
#     'app.tasks.translation.process_batch_task': {'queue': 'translation'},
# }

