"""Project management API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.db_models import User, Project, ProjectStatus, Page, PageStatus
from app.models.schemas import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new book translation project."""
    new_project = Project(
        user_id=current_user.id,
        title=project_data.title,
        author=project_data.author,
        source_language=project_data.source_language,
        target_language=project_data.target_language,
        book_context=project_data.book_context,
        status=ProjectStatus.CREATED
    )
    
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    
    return new_project


@router.get("", response_model=ProjectListResponse)
def list_projects(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all projects for the current user."""
    query = db.query(Project).filter(Project.user_id == current_user.id)
    total = query.count()
    projects = query.order_by(Project.created_at.desc()).offset(skip).limit(limit).all()
    
    return {"projects": projects, "total": total}


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific project by ID."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update project metadata."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Update fields
    if project_data.title is not None:
        project.title = project_data.title
    if project_data.author is not None:
        project.author = project_data.author
    if project_data.book_context is not None:
        project.book_context = project_data.book_context
    
    db.commit()
    db.refresh(project)
    
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a project and all its pages."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Delete from database (cascade will handle pages)
    db.delete(project)
    db.commit()
    
    # TODO: Delete files from GCS in background task
    # from app.services.storage import storage_service
    # storage_service.delete_project_files(project_id)
    
    return None


@router.post("/{project_id}/reset-pages")
def reset_project_pages(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reset all pages in a project to UPLOADED status for re-processing."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Update all pages
    db.query(Page).filter(
        Page.project_id == project_id
    ).update({
        "status": PageStatus.UPLOADED,
        "error_message": None,
        "quality_score": None,
        "quality_level": None
    }, synchronize_session=False)
    
    # Reset project stats
    project.completed_pages = 0
    project.status = ProjectStatus.CREATED
    
    db.commit()
    db.refresh(project)
    
    return {"message": "All pages reset to UPLOADED status", "project_id": project_id}


from pydantic import BaseModel
class BatchUpdateStatusRequest(BaseModel):
    status: str
    page_ids: Optional[List[int]] = None  # None means ALL pages

@router.post("/{project_id}/pages/batch-update")
def batch_update_page_status(
    project_id: int,
    update_request: BatchUpdateStatusRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update status for multiple pages."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    # validate status
    valid_statuses = [s.value for s in PageStatus]
    if update_request.status not in valid_statuses:
         raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {valid_statuses}")
    
    query = db.query(Page).filter(Page.project_id == project_id)
    
    if update_request.page_ids:
        query = query.filter(Page.id.in_(update_request.page_ids))
        
    updated_count = query.update({
        "status": update_request.status,
        "error_message": None if update_request.status == PageStatus.UPLOADED else Page.error_message
    }, synchronize_session=False)
    
    db.commit()
    return {"message": f"Updated {updated_count} pages to {update_request.status}"}


@router.get("/{project_id}/progress")
def get_project_progress(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get live aggregated progress stats for a project."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Efficiently count by status using GROUP BY
    from sqlalchemy import func
    stats = db.query(
        Page.status, func.count(Page.id)
    ).filter(
        Page.project_id == project_id
    ).group_by(Page.status).all()
    
    result = {
        "total": 0,
        "uploaded": 0,
        "queued": 0,
        "processing": 0,
        "completed": 0,
        "failed": 0,
        "needs_review": 0
    }
    
    for status_enum, count in stats:
        # Map enum to string key if needed, or use value
        if hasattr(status_enum, 'value'):
            status_key = status_enum.value.lower()
        else:
            status_key = str(status_enum).lower()
            
        result[status_key] = count
        result["total"] += count

    # Calculate speed (pages per minute in last 5 mins)
    from datetime import datetime, timedelta
    five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
    
    recent_completed = db.query(Page).filter(
        Page.project_id == project_id,
        Page.status == PageStatus.COMPLETED,
        Page.processed_at >= five_mins_ago
    ).count()
    
    # PPM = recent_completed / 5 minutes
    ppm = recent_completed / 5.0
    result["pages_per_minute"] = round(ppm, 2)
    
    # Estimate remaining time
    remaining = result.get("queued", 0) + result.get("processing", 0) + result.get("uploaded", 0)
    
    if ppm > 0.1: # Threshold to avoid massive numbers
        minutes_left = remaining / ppm
        result["estimated_minutes_remaining"] = round(minutes_left, 1)
    else:
        result["estimated_minutes_remaining"] = None
        
    return result


@router.get("/{project_id}/download-book")
def download_complete_book(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Merge all completed page PDFs into a single book."""
    from PyPDF2 import PdfMerger
    from pathlib import Path
    from fastapi.responses import FileResponse
    import logging
    
    logger = logging.getLogger(__name__)
    
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get all completed pages in order
    pages = db.query(Page).filter(
        Page.project_id == project_id,
        Page.status == PageStatus.COMPLETED,
        Page.output_pdf_path.isnot(None)
    ).order_by(Page.page_number).all()
    
    if not pages:
        raise HTTPException(status_code=404, detail="No completed pages found")
    
    # Merge PDFs
    merger = PdfMerger()
    
    import tempfile
    import os
    
    # Create a temporary directory to hold downloaded PDFs
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            from app.services.storage import storage_service
            
            for page in pages:
                # Get the actual file path
                if storage_service.use_local:
                    pdf_path = storage_service.get_local_path(page.output_pdf_path, is_output=True)
                else:
                    # Download from GCS to temp file
                    try:
                        blob_path = page.output_pdf_path
                        blob = storage_service.outputs_bucket.blob(blob_path)
                        local_filename = os.path.join(temp_dir, f"page_{page.page_number}.pdf")
                        print(f"[Storage] Downloading {blob_path} to {local_filename}...")
                        blob.download_to_filename(local_filename, timeout=60)
                        print("[Storage] Download complete.")
                        pdf_path = local_filename
                    except Exception as e:
                        logger.error(f"Failed to download PDF from GCS for page {page.page_number}: {e}")
                        pdf_path = None
                
                if pdf_path and Path(pdf_path).exists():
                    merger.append(pdf_path)
                else:
                    logger.warning(f"PDF not found for page {page.page_number}: {pdf_path}")
            
            # Save merged PDF
            output_filename = f"{project.title.replace(' ', '_')}_complete.pdf"
            output_path = Path("output") / output_filename
            output_path.parent.mkdir(exist_ok=True)
            
            merger.write(str(output_path))
            merger.close()
            
            # Return file for download
            return FileResponse(
                path=str(output_path),
                media_type="application/pdf",
                filename=output_filename
            )
            
        except Exception as e:
            merger.close()
            raise HTTPException(status_code=500, detail=f"Failed to merge PDFs: {str(e)}")
