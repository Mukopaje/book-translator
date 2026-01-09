"""Background tasks for page translation."""
import os
import sys
import logging
from pathlib import Path
from celery import Task
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.db_models import Page, Project, PageStatus
from app.services.storage import storage_service
from datetime import datetime

# Add project root to path for BookTranslator import
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

logger = logging.getLogger(__name__)


class DBTask(Task):
    """Base task with database session management."""
    _db = None
    
    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db
    
    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(bind=True, base=DBTask, name='app.tasks.translation.process_page_task')
def process_page_task(self, page_id: int, project_id: int):
    """
    Process a single page: OCR, translate, generate PDF.
    
    Args:
        page_id: Database ID of the page
        project_id: Database ID of the project
    """
    db = self.db
    
    try:
        # Get page from database
        page = db.query(Page).filter(Page.id == page_id).first()
        if not page:
            raise ValueError(f"Page {page_id} not found")
        
        # Get project for context
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        # Update status to processing
        page.status = PageStatus.PROCESSING
        db.commit()
        
        logger.info(f"Starting processing for page {page_id} (page #{page.page_number})")
        
        # Download image from GCS if needed
        from app.config import settings
        if settings.use_local_storage:
            image_path = storage_service.get_local_path(
                settings.gcs_bucket_originals,
                page.original_image_path
            )
        else:
            # Download from GCS to temp location
            import tempfile
            import requests
            
            signed_url = storage_service.get_signed_url(
                settings.gcs_bucket_originals,
                page.original_image_path,
                expiration=3600
            )
            
            temp_dir = tempfile.mkdtemp()
            image_path = os.path.join(temp_dir, f"page_{page_id}.jpg")
            
            response = requests.get(signed_url.replace('file://', ''))
            with open(image_path, 'wb') as f:
                f.write(response.content)
        
        # Import BookTranslator
        from main import BookTranslator
        
        # Process the page
        output_dir = str(project_root / "output")
        os.makedirs(output_dir, exist_ok=True)
        
        translator = BookTranslator(
            image_path,
            output_dir,
            book_context=project.book_context or ''
        )
        
        results = translator.process_page(verbose=True)
        
        if results.get('success'):
            # Extract results
            ocr_text = results.get('steps', {}).get('ocr_extraction', {}).get('preview', '')
            trans_text = results.get('steps', {}).get('translation', {}).get('preview', '')
            
            # Get PDF path
            stem = Path(image_path).stem
            pdf_path = os.path.join(output_dir, f"{stem}_translated.pdf")
            
            if not os.path.exists(pdf_path):
                raise FileNotFoundError(f"PDF not created: {pdf_path}")
            
            # Upload PDF to GCS if enabled
            if not settings.use_local_storage:
                output_gcs_path = storage_service.upload_output_pdf(
                    pdf_path,
                    project_id,
                    page.page_number
                )
            else:
                output_gcs_path = pdf_path

            # Persist artifacts JSON (if present)
            try:
                artifact_details = results.get('steps', {}).get('artifact_details')
                if artifact_details:
                    import json
                    artifact_json_path = os.path.join(output_dir, f"{stem}_artifacts.json")
                    with open(artifact_json_path, 'w', encoding='utf-8') as jf:
                        json.dump(artifact_details, jf, ensure_ascii=False, indent=2)

                    # Upload alongside PDF when using GCS
                    storage_service.upload_artifacts_json(
                        artifact_json_path,
                        project_id,
                        page.page_number,
                    )
            except Exception as e:
                logger.warning(f"Failed to persist artifacts JSON for page {page_id}: {e}")
            
            # Update page in database
            page.status = PageStatus.COMPLETED
            page.ocr_text = ocr_text
            page.translated_text = trans_text
            page.output_pdf_path = output_gcs_path
            page.processed_at = datetime.utcnow()
            
            # Update project progress
            completed = db.query(Page).filter(
                Page.project_id == project_id,
                Page.status == PageStatus.COMPLETED
            ).count()
            project.completed_pages = completed
            
            db.commit()
            
            logger.info(f"✅ Page {page_id} completed successfully")
            
            return {
                'status': 'completed',
                'page_id': page_id,
                'page_number': page.page_number,
                'ocr_chars': len(ocr_text),
                'trans_chars': len(trans_text)
            }
        else:
            # Processing failed
            error_msg = results.get('error', 'Unknown error')
            page.status = PageStatus.FAILED
            page.error_message = error_msg
            db.commit()
            
            logger.error(f"❌ Page {page_id} failed: {error_msg}")
            raise Exception(error_msg)
    
    except Exception as e:
        # Mark as failed
        logger.exception(f"Error processing page {page_id}")
        
        try:
            page = db.query(Page).filter(Page.id == page_id).first()
            if page:
                page.status = PageStatus.FAILED
                page.error_message = str(e)
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update page status: {db_error}")
        
        raise


@celery_app.task(bind=True, base=DBTask, name='app.tasks.translation.process_batch_task')
def process_batch_task(self, project_id: int, page_ids: list):
    """
    Process multiple pages in sequence.
    
    Args:
        project_id: Database ID of the project
        page_ids: List of page IDs to process
    """
    db = self.db
    results = []
    
    logger.info(f"Starting batch processing for {len(page_ids)} pages in project {project_id}")
    
    for i, page_id in enumerate(page_ids, 1):
        try:
            logger.info(f"Processing page {i}/{len(page_ids)}: {page_id}")
            
            # Update progress
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': i,
                    'total': len(page_ids),
                    'page_id': page_id,
                    'status': 'processing'
                }
            )
            
            # Process the page
            # Execute synchronously using apply() to ensure proper context
            task_result = process_page_task.apply(args=[page_id, project_id])
            
            if task_result.failed():
                raise task_result.result
                
            result = task_result.result
            results.append(result)
            
        except Exception as e:
            logger.error(f"Failed to process page {page_id}: {e}")
            results.append({
                'status': 'failed',
                'page_id': page_id,
                'error': str(e)
            })
    
    # Calculate statistics
    completed = sum(1 for r in results if r['status'] == 'completed')
    failed = len(results) - completed
    
    logger.info(f"Batch processing complete: {completed} succeeded, {failed} failed")
    
    return {
        'total': len(page_ids),
        'completed': completed,
        'failed': failed,
        'results': results
    }
