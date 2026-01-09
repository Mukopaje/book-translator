"""Job management API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models.db_models import User, Page, PageStatus
from app.api.dependencies import get_current_user
from app.tasks.translation import process_page_task, process_batch_task
from celery.result import AsyncResult
from app.celery_app import celery_app

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/process-page/{page_id}")
def queue_page_processing(
    page_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Queue a page for async processing."""
    # Get page and verify ownership
    page = db.query(Page).filter(Page.id == page_id).first()
    if not page:
        raise HTTPException(404, "Page not found")
    
    # Verify user owns the project
    if page.project.user_id != current_user.id:
        raise HTTPException(403, "Access denied")
    
    # Update page status
    page.status = PageStatus.QUEUED
    db.commit()
    
    # Queue task
    task = process_page_task.apply_async(
        args=[page_id, page.project_id],
        task_id=f"page_{page_id}"
    )
    
    return {
        "task_id": task.id,
        "page_id": page_id,
        "status": "queued"
    }


@router.post("/process-batch")
def queue_batch_processing(
    page_ids: list[int],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Queue multiple pages for processing."""
    # Verify all pages exist and user owns them
    pages = db.query(Page).filter(Page.id.in_(page_ids)).all()
    
    if len(pages) != len(page_ids):
        raise HTTPException(404, "Some pages not found")
    
    for page in pages:
        if page.project.user_id != current_user.id:
            raise HTTPException(403, "Access denied")
        page.status = PageStatus.QUEUED
    
    db.commit()
    
    # Get project_id (all pages should be from same project)
    project_id = pages[0].project_id
    
    # Queue batch task
    task = process_batch_task.apply_async(args=[project_id, page_ids])
    
    return {
        "task_id": task.id,
        "page_ids": page_ids,
        "status": "queued"
    }


@router.get("/status/{task_id}")
def get_task_status(task_id: str):
    """Get status of a background task."""
    task = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "state": task.state,
        "ready": task.ready(),
        "successful": task.successful() if task.ready() else None,
    }
    
    if task.state == 'PROGRESS':
        response['meta'] = task.info
    elif task.state == 'SUCCESS':
        response['result'] = task.result
    elif task.state == 'FAILURE':
        response['error'] = str(task.info)
    
    return response


@router.get("/page-status/{page_id}")
def get_page_processing_status(
    page_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current processing status of a page."""
    page = db.query(Page).filter(Page.id == page_id).first()
    if not page:
        raise HTTPException(404, "Page not found")
    
    if page.project.user_id != current_user.id:
        raise HTTPException(403, "Access denied")
    
    # Check if there's an active task
    task_id = f"page_{page_id}"
    task = AsyncResult(task_id, app=celery_app)
    
    return {
        "page_id": page_id,
        "status": page.status,
        "task_state": task.state if task else None,
        "task_ready": task.ready() if task else None,
        "error": page.error_message
    }


@router.delete("/cancel/{task_id}")
def cancel_task(task_id: str):
    """Cancel a running task."""
    celery_app.control.revoke(task_id, terminate=True)
    return {"message": "Task cancelled", "task_id": task_id}
