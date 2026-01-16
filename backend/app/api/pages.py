"""Page management API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models.db_models import User, Project, Page, PageStatus, ProjectStatus
from app.models.schemas import PageResponse, PageListResponse, PageUpdate
from app.api.dependencies import get_current_user
from app.services.storage import storage_service
from datetime import datetime

router = APIRouter(prefix="/projects/{project_id}/pages", tags=["pages"])


def verify_project_access(project_id: int, user: User, db: Session) -> Project:
    """Verify user has access to the project."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project


@router.post("", response_model=PageResponse, status_code=status.HTTP_201_CREATED)
async def upload_page(
    project_id: int,
    page_number: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a new page image to a project."""
    # Verify access
    project = verify_project_access(project_id, current_user, db)

    # CREDIT CHECK: Enforce limits
    if current_user.used_credits >= current_user.total_credits:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"You have reached your limit of {current_user.total_credits} pages. Please upgrade your subscription."
        )
    
    # Check if page number already exists
    existing_page = db.query(Page).filter(
        Page.project_id == project_id,
        Page.page_number == page_number
    ).first()
    
    if existing_page:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Page {page_number} already exists in this project"
        )
    
    # Upload to GCS
    gcs_path = storage_service.upload_original_image(
        file.file,
        project_id,
        page_number,
        file.filename
    )
    
    # Create page record
    new_page = Page(
        project_id=project_id,
        page_number=page_number,
        original_image_path=gcs_path,
        status=PageStatus.UPLOADED
    )
    
    db.add(new_page)
    
    # Update project totals
    project.total_pages += 1
    if project.status == ProjectStatus.CREATED:
        project.status = ProjectStatus.PROCESSING
    
    # Consume 1 credit
    current_user.used_credits += 1
    
    db.commit()
    db.refresh(new_page)
    
    # TODO: Trigger async processing task here
    # process_page_task.delay(new_page.id)
    
    return new_page


@router.get("", response_model=PageListResponse)
def list_pages(
    project_id: int,
    skip: int = 0,
    limit: int = 20,  # Default to 20 pages per request for better performance
    status_filter: str = None,  # Optional: filter by status (e.g., "COMPLETED", "NEEDS_REVIEW")
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List pages in a project with pagination and optional filtering.

    Args:
        project_id: Project ID
        skip: Number of pages to skip (for pagination)
        limit: Maximum number of pages to return (default: 20, max: 1000)
        status_filter: Optional status filter (UPLOADED, PROCESSING, COMPLETED, FAILED, NEEDS_REVIEW)
    """
    # Verify access
    verify_project_access(project_id, current_user, db)

    # Limit the maximum page size to prevent overload
    limit = min(limit, 1000)

    # Build query with optional status filter
    query = db.query(Page).filter(Page.project_id == project_id)

    if status_filter:
        # Handle multiple statuses separated by comma
        statuses = [s.strip().upper() for s in status_filter.split(',')]
        valid_statuses = [s for s in statuses if s in PageStatus.__members__]
        if valid_statuses:
            query = query.filter(Page.status.in_(valid_statuses))

    # Get total count before pagination
    total = query.count()

    # Apply pagination and ordering
    pages = query.order_by(Page.page_number).offset(skip).limit(limit).all()

    return {"pages": pages, "total": total}


@router.get("/{page_id}", response_model=PageResponse)
def get_page(
    project_id: int,
    page_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific page by ID."""
    # Verify access
    verify_project_access(project_id, current_user, db)
    
    page = db.query(Page).filter(
        Page.id == page_id,
        Page.project_id == project_id
    ).first()
    
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page not found"
        )
    
    return page


@router.patch("/{page_id}", response_model=PageResponse)
def update_page(
    project_id: int,
    page_id: int,
    update_data: PageUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update page details after processing."""
    from datetime import datetime
    
    # Verify access
    verify_project_access(project_id, current_user, db)
    
    page = db.query(Page).filter(
        Page.id == page_id,
        Page.project_id == project_id
    ).first()
    
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page not found"
        )
    
    # Update fields if provided
    if update_data.status:
        page.status = update_data.status
    if update_data.ocr_text is not None:
        page.ocr_text = update_data.ocr_text
    if update_data.translated_text is not None:
        page.translated_text = update_data.translated_text
    if update_data.output_pdf_path is not None:
        page.output_pdf_path = update_data.output_pdf_path
    
    # Set processed_at timestamp when completed
    if update_data.status == 'completed':
        page.processed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(page)
    
    return page


@router.get("/{page_id}/download")
def get_download_url(
    project_id: int,
    page_id: int,
    file_type: str = "pdf",  # "pdf" or "original"
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a signed URL for downloading a page file."""
    # Verify access
    verify_project_access(project_id, current_user, db)
    
    page = db.query(Page).filter(
        Page.id == page_id,
        Page.project_id == project_id
    ).first()
    
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page not found"
        )
    
    # Determine which file to download
    if file_type == "pdf":
        if not page.output_pdf_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PDF not yet generated for this page"
            )
        bucket_name = "gcs_bucket_outputs"
        blob_path = page.output_pdf_path
    else:  # original
        bucket_name = "gcs_bucket_originals"
        blob_path = page.original_image_path
    
    # Generate signed URL
    from app.config import settings
    bucket = getattr(settings, bucket_name)
    signed_url = storage_service.get_signed_url(bucket, blob_path, expiration=3600)
    
    return {"url": signed_url, "expires_in": 3600}


@router.put("/{page_id}/replace-image", response_model=PageResponse)
async def replace_page_image(
    project_id: int,
    page_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Replace the input image for a page and reset its processing status.
    Useful when the original scan quality was poor and affecting output quality.

    Args:
        project_id: Project ID
        page_id: Page ID
        file: New image file to replace the original

    Returns:
        Updated page with reset status
    """
    # Verify access
    verify_project_access(project_id, current_user, db)

    page = db.query(Page).filter(
        Page.id == page_id,
        Page.project_id == project_id
    ).first()

    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page not found"
        )

    # Store previous status to adjust project counts
    was_completed = page.status in [PageStatus.COMPLETED, PageStatus.NEEDS_REVIEW]

    # Upload new image to storage
    new_gcs_path = storage_service.upload_original_image(
        file.file,
        project_id,
        page.page_number,
        file.filename or f"page_{page.page_number}_replaced.jpg"
    )

    # Reset page status and clear previous results
    page.original_image_path = new_gcs_path
    page.status = PageStatus.UPLOADED
    page.error_message = None
    page.quality_score = None
    page.quality_level = None
    page.quality_issues = None
    page.quality_recommendations = None
    page.ocr_text = None
    page.translated_text = None
    page.output_pdf_path = None
    page.processed_at = None
    page.replaced_at = datetime.utcnow()

    # Update project completed count if this was previously completed
    if was_completed:
        project = page.project
        project.completed_pages = max(0, project.completed_pages - 1)

    db.commit()
    db.refresh(page)

    return page


@router.delete("/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_page(
    project_id: int,
    page_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a page."""
    # Verify access
    project = verify_project_access(project_id, current_user, db)
    
    page = db.query(Page).filter(
        Page.id == page_id,
        Page.project_id == project_id
    ).first()
    
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page not found"
        )
    
    # Delete from database
    db.delete(page)
    
    # Update project totals
    project.total_pages -= 1
    if page.status == PageStatus.COMPLETED:
        project.completed_pages -= 1
    
    db.commit()
    
    # TODO: Delete files from GCS in background task
    
    return None
