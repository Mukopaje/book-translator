"""Task management API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
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


@router.post("/maintenance/cleanup-stuck")
def cleanup_stuck_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Identify and reset tasks that are stuck in 'PROCESSING' state.
    This handles cases where the worker crashed or was restarted.
    Resets status to QUEUED and re-dispatches the task.
    """
    # Find all pages stuck in PROCESSING status
    stuck_pages = db.query(Page).filter(
        Page.status == PageStatus.PROCESSING
    ).all()
    
    count = 0
    requeued = 0
    
    from app.tasks.translation import process_page_task
    
    for page in stuck_pages:
        # Reset status
        page.status = PageStatus.QUEUED
        count += 1
        
        # Re-queue
        try:
            process_page_task.delay(page.id, page.project_id)
            requeued += 1
        except Exception as e:
            print(f"Failed to re-queue page {page.id}: {e}")
            page.status = PageStatus.FAILED
            page.error_message = f"Stuck task cleanup failed to re-queue: {str(e)}"
            
    db.commit()
    
    return {
        "message": f"Found {count} stuck pages. Reset and re-queued {requeued} tasks.",
        "reset_count": count,
        "requeued_count": requeued
    }


@router.get("/public/info")
def get_public_info():
    """Get public site information for the landing page."""
    from app.config import settings
    return {
        "company_name": settings.company_name,
        "company_logo_url": settings.company_logo_url,
        "company_logo_size": settings.company_logo_size,
        "site_primary_color": settings.site_primary_color,
        "site_secondary_color": settings.site_secondary_color,
        "site_contact_info": settings.site_contact_info,
        "example_screenshots": settings.example_screenshots.split(",") if settings.example_screenshots else []
    }


@router.get("/admin/stats")
def get_admin_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get system-wide statistics for the super admin."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin only."
        )
    
    from sqlalchemy import func
    from app.models.db_models import Project, Page, User
    
    total_users = db.query(User).count()
    total_projects = db.query(Project).count()
    total_pages = db.query(Page).count()
    completed_pages = db.query(Page).filter(Page.status == 'COMPLETED').count()
    failed_pages = db.query(Page).filter(Page.status == 'FAILED').count()
    
    # MRR (roughly based on non-free status)
    premium_users = db.query(User).filter(User.subscription_status != 'free').count()
    
    from app.config import settings
    
    # Financial metrics (Placeholder for Stripe API calls)
    estimated_mrr = premium_users * 29.0 # Simple estimation
    
    return {
        "total_users": total_users,
        "total_projects": total_projects,
        "total_pages": total_pages,
        "completed_pages": completed_pages,
        "failed_pages": failed_pages,
        "premium_users": premium_users,
        "queue_latency": "Low",
        "stripe_configured": bool(settings.stripe_api_key),
        "financials": {
             "mrr": estimated_mrr,
             "total_revenue": estimated_mrr * 1.5, # Placeholder
             "currency": "USD"
        },
        "example_screenshots": settings.example_screenshots.split(",") if settings.example_screenshots else [],
        "settings": {
             "company_name": settings.company_name,
             "company_address": settings.company_address,
             "company_email": settings.company_email,
             "company_phone": settings.company_phone,
             "company_logo_url": settings.company_logo_url,
             "company_logo_size": settings.company_logo_size,
             "site_primary_color": settings.site_primary_color,
             "site_secondary_color": settings.site_secondary_color,
             "site_contact_info": settings.site_contact_info,
             "smtp_server": settings.smtp_server,
             "smtp_port": settings.smtp_port,
             "smtp_user": settings.smtp_user
        }
    }


@router.post("/admin/upload-portfolio")
async def upload_portfolio_item(
    original: UploadFile = File(...),
    translated: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a portfolio pair to GCS and update system config (Admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    
    # Upload both to public bucket
    from app.services.storage import storage_service
    from app.config import settings
    
    # Use a specific 'portfolio' folder in the outputs bucket or a new public one
    bucket = settings.gcs_bucket_outputs
    
    orig_path = f"portfolio/{uuid.uuid4()}_{original.filename}"
    trans_path = f"portfolio/{uuid.uuid4()}_{translated.filename}"
    
    storage_service.upload_file(original.file, bucket, orig_path)
    storage_service.upload_file(translated.file, bucket, trans_path)
    
    # Get public URLs (assuming bucket is public or using signed URLs)
    orig_url = storage_service.get_signed_url(bucket, orig_path, expiration=31536000) # 1 year
    trans_url = storage_service.get_signed_url(bucket, trans_path, expiration=31536000)
    
    pair = f"{orig_url}|{trans_url}"
    
    # Update settings
    current = settings.example_screenshots
    new_val = f"{current},{pair}" if current else pair
    settings.example_screenshots = new_val
    
    return {"success": True, "pair": pair}


class GiveCreditsRequest(BaseModel):
    user_id: int
    amount: int


@router.post("/admin/give-credits")
def give_credits(
    request: GiveCreditsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Grant credits to a specific user (Admin only)."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin only."
        )
    
    target_user = db.query(User).filter(User.id == request.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    target_user.total_credits += request.amount
    db.commit()
    
    return {
        "success": True,
        "message": f"Added {request.amount} credits to {target_user.email}",
        "new_total": target_user.total_credits
    }

@router.get("/admin/users")
def list_users_for_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all users for administration (Admin only)."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin only."
        )
    
    users = db.query(User).all()
    return [{
        "id": u.id,
        "email": u.email,
        "total_credits": u.total_credits,
        "used_credits": u.used_credits,
        "subscription_status": u.subscription_status,
        "is_admin": u.is_admin
    } for u in users]


@router.get("/admin/documents")
def list_billing_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all billing documents for CRM (Admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    
    from app.models.db_models import BillingDocument
    docs = db.query(BillingDocument).order_by(BillingDocument.created_at.desc()).all()
    return docs


class CreateDocumentRequest(BaseModel):
    user_id: int
    doc_type: str # QUOTATION, INVOICE, RECEIPT
    amount: float
    items: List[dict]
    currency: Optional[str] = "USD"
    tax_rate: Optional[float] = 0.0
    discount_rate: Optional[float] = 0.0
    notes: Optional[str] = None
    due_date: Optional[datetime] = None


@router.post("/admin/documents")
def create_billing_document(
    request: CreateDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a professional billing document (Admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    
    from app.models.db_models import BillingDocument, User as UserModel
    from app.services.billing_service import BillingPDFGenerator
    from app.config import settings
    import uuid
    import json
    
    target_user = db.query(UserModel).filter(UserModel.id == request.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    doc_id = str(uuid.uuid4())
    items_json = json.dumps(request.items)
    
    company_info = {
        "company_name": settings.company_name,
        "company_address": settings.company_address
    }
    
    # Generate PDF
    pdf_gen = BillingPDFGenerator()
    pdf_path = pdf_gen.generate_document(
        doc_id=doc_id,
        doc_type=request.doc_type,
        user_email=target_user.email,
        amount=request.amount,
        items_json=items_json,
        status="PAID" if request.doc_type == "RECEIPT" else "SENT",
        currency=request.currency,
        tax_rate=request.tax_rate,
        discount_rate=request.discount_rate,
        notes=request.notes,
        due_date=request.due_date.strftime('%Y-%m-%d') if request.due_date else None,
        company_info=company_info
    )
    
    new_doc = BillingDocument(
        id=doc_id,
        user_id=request.user_id,
        doc_type=request.doc_type,
        amount=request.amount,
        items=items_json,
        currency=request.currency,
        tax_rate=request.tax_rate,
        discount_rate=request.discount_rate,
        notes=request.notes,
        due_date=request.due_date,
        status="PAID" if request.doc_type == "RECEIPT" else "SENT",
        pdf_gcs_path=pdf_path
    )
    
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    
    return new_doc


@router.post("/admin/documents/{doc_id}/convert")
def convert_quotation_to_invoice(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Convert an existing QUOTATION to an INVOICE."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    
    from app.models.db_models import BillingDocument, User as UserModel
    from app.services.billing_service import BillingPDFGenerator
    from app.config import settings
    import uuid
    
    old_doc = db.query(BillingDocument).filter(BillingDocument.id == doc_id).first()
    if not old_doc or old_doc.doc_type != "QUOTATION":
        raise HTTPException(status_code=400, detail="Valid Quotation not found")
    
    new_id = str(uuid.uuid4())
    target_user = db.query(UserModel).filter(UserModel.id == old_doc.user_id).first()

    company_info = {
        "company_name": settings.company_name,
        "company_address": settings.company_address
    }
    
    # Generate new PDF for Invoice
    pdf_gen = BillingPDFGenerator()
    pdf_path = pdf_gen.generate_document(
        doc_id=new_id,
        doc_type="INVOICE",
        user_email=target_user.email,
        amount=old_doc.amount,
        items_json=old_doc.items,
        status="SENT",
        currency=old_doc.currency,
        tax_rate=old_doc.tax_rate,
        discount_rate=old_doc.discount_rate,
        notes=old_doc.notes,
        company_info=company_info
    )
    
    new_doc = BillingDocument(
        id=new_id,
        user_id=old_doc.user_id,
        doc_type="INVOICE",
        amount=old_doc.amount,
        items=old_doc.items,
        currency=old_doc.currency,
        tax_rate=old_doc.tax_rate,
        discount_rate=old_doc.discount_rate,
        notes=old_doc.notes,
        status="SENT",
        pdf_gcs_path=pdf_path
    )
    
    # Mark old quote as VOID or COMPLETED?
    old_doc.status = "PAID" # Logic: accepted quotes are closed
    
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    
    return new_doc


class StripeConfigRequest(BaseModel):
    stripe_api_key: str
    stripe_webhook_secret: str
    price_id_pro: str
    price_id_scale: str
    example_screenshots: Optional[str] = None


@router.post("/admin/config")
def update_system_config(
    request: StripeConfigRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update Stripe configuration (Admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    
    # In a real production app, we'd save this to a 'settings' table or Vault.
    # For now, we suggest adding to .env for persistence across restarts.
    return {
        "success": True,
        "message": "Stripe configuration received. Note: Permanent persistence requires updating the server .env file."
    }


@router.post("/billing/create-checkout-session")
def create_checkout_session(
    plan: str, # "pro" or "scale"
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a Stripe Checkout Session for subscription."""
    import stripe
    from app.config import settings
    
    if not settings.stripe_api_key:
        raise HTTPException(status_code=500, detail="Stripe is not configured")
    
    stripe.api_key = settings.stripe_api_key
    
    price_id = settings.stripe_price_id_pro if plan == "pro" else settings.stripe_price_id_scale
    
    try:
        checkout_session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription',
            success_url=f"{settings.allowed_origins}/?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.allowed_origins}/",
            metadata={"user_id": current_user.id, "plan": plan}
        )
        return {"url": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
