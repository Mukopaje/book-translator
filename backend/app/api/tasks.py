"""Task management API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List
from app.database import get_db
from app.models.db_models import User, Project, Page
from app.api.dependencies import get_current_user
from app.api.pages import verify_project_access
from celery.result import AsyncResult
from app.celery_app import celery_app
from pydantic import BaseModel

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskResponse(BaseModel):
    task_id: str
    status: str
    current: Optional[int] = None
    total: Optional[int] = None
    result: Optional[dict] = None


class BatchProcessRequest(BaseModel):
    page_ids: List[int]


@router.post("/projects/{project_id}/process-page/{page_id}")
def queue_page_processing(
    project_id: int,
    page_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Queue a single page for background processing."""
    # Verify access
    verify_project_access(project_id, current_user, db)
    
    # Verify page exists
    page = db.query(Page).filter(
        Page.id == page_id,
        Page.project_id == project_id
    ).first()
    
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page not found"
        )
    
    # Queue the task
    from app.tasks.translation import process_page_task
    task = process_page_task.delay(page_id, project_id)
    
    # Update page status
    page.status = 'queued'
    db.commit()
    
    return {
        "task_id": task.id,
        "status": "queued",
        "page_id": page_id,
        "page_number": page.page_number
    }


@router.post("/projects/{project_id}/process-batch")
def queue_batch_processing(
    project_id: int,
    request: BatchProcessRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Queue multiple pages for background processing."""
    # Verify access
    verify_project_access(project_id, current_user, db)
    
    # Verify all pages exist
    pages = db.query(Page).filter(
        Page.id.in_(request.page_ids),
        Page.project_id == project_id
    ).all()
    
    if len(pages) != len(request.page_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Some page IDs are invalid"
        )
    
    # Queue the batch task
    from app.tasks.translation import process_batch_task
    task = process_batch_task.delay(project_id, request.page_ids)
    
    # Update all pages to queued status
    for page in pages:
        page.status = 'queued'
    db.commit()
    
    return {
        "task_id": task.id,
        "status": "queued",
        "total_pages": len(request.page_ids),
        "page_ids": request.page_ids
    }


@router.get("/status/{task_id}", response_model=TaskResponse)
def get_task_status(task_id: str):
    """Get the status of a background task."""
    task = AsyncResult(task_id, app=celery_app)
    
    if task.state == 'PENDING':
        response = {
            'task_id': task_id,
            'status': 'pending',
            'current': 0,
            'total': 1
        }
    elif task.state == 'PROGRESS':
        response = {
            'task_id': task_id,
            'status': 'processing',
            'current': task.info.get('current', 0),
            'total': task.info.get('total', 1)
        }
    elif task.state == 'SUCCESS':
        response = {
            'task_id': task_id,
            'status': 'completed',
            'result': task.result
        }
    elif task.state == 'FAILURE':
        response = {
            'task_id': task_id,
            'status': 'failed',
            'result': {'error': str(task.info)}
        }
    else:
        response = {
            'task_id': task_id,
            'status': task.state.lower()
        }
    
    return response


@router.post("/cancel/{task_id}")
def cancel_task(task_id: str):
    """Cancel a running task."""
    task = AsyncResult(task_id, app=celery_app)
    task.revoke(terminate=True)
    
    return {
        "task_id": task_id,
        "status": "cancelled"
    }
