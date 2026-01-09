"""Celery background tasks for page processing."""
import os
import sys
from pathlib import Path
from celery import Task
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.db_models import Page, Project
from datetime import datetime

# Add parent directory to path to import BookTranslator
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.main import BookTranslator


class DatabaseTask(Task):
    """Base task that provides database session."""
    _db = None
    
    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db
    
    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()


@celery_app.task(base=DatabaseTask, bind=True, name="process_page")
def process_page_task(self, page_id: int, project_id: int):
    """Process a single page: OCR, translate, generate PDF."""
    db = self.db
    
    try:
        # Update task info
        self.update_state(state='PROGRESS', meta={'status': 'Loading page...'})
        
        # Get page from database
        page = db.query(Page).filter(Page.id == page_id).first()
        if not page:
            raise Exception(f"Page {page_id} not found")
        
        # Get project for context
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise Exception(f"Project {project_id} not found")
        
        # Update status to processing
        page.status = 'processing'
        db.commit()
        
        self.update_state(state='PROGRESS', meta={'status': 'Downloading image...'})
        
        # Download image from GCS to temp location
        from app.services.storage import storage_service
        from app.config import settings
        
        temp_dir = Path("temp_processing")
        temp_dir.mkdir(exist_ok=True)
        
        # Download from GCS
        local_path = temp_dir / f"page_{page_id}.jpg"
        
        if settings.use_local_storage:
            # Copy from local storage
            import shutil
            source_path = Path(page.original_image_path)
            if source_path.exists():
                shutil.copy2(source_path, local_path)
            else:
                raise Exception(f"Source file not found: {source_path}")
        else:
            # Download from GCS
            blob_name = page.original_image_path
            destination_file_name = str(local_path)
            print(f"[Storage] Downloading {blob_name} to {destination_file_name}...")
            blob = storage_service.storage_client.bucket(settings.gcs_bucket_originals).blob(blob_name)
            blob.download_to_filename(destination_file_name, timeout=60)
            print("[Storage] Download complete.")
        
        self.update_state(state='PROGRESS', meta={'status': 'Processing page...'})
        
        # Process with BookTranslator
        output_dir = Path("output_temp")
        output_dir.mkdir(exist_ok=True)
        
        translator = BookTranslator(
            str(local_path),
            str(output_dir),
            book_context=project.book_context or ""
        )
        
        results = translator.process_page(verbose=True)
        
        if not results.get('success'):
            raise Exception(results.get('error', 'Translation failed'))
        
        self.update_state(state='PROGRESS', meta={'status': 'Saving results...'})
        
        # Get output PDF path
        stem = local_path.stem
        pdf_path = output_dir / f"{stem}_translated.pdf"
        
        if not pdf_path.exists():
            raise Exception("PDF was not created")
        
        # Upload PDF to GCS
        if settings.use_local_storage:
            # Store locally
            final_output_dir = Path("backend/storage/outputs")
            final_output_dir.mkdir(parents=True, exist_ok=True)
            final_pdf_path = final_output_dir / f"page_{page_id}_{stem}_translated.pdf"
            import shutil
            shutil.copy2(pdf_path, final_pdf_path)
            output_pdf_path = str(final_pdf_path)
        else:
            # Upload to GCS
            output_pdf_path = storage_service.upload_output_pdf(
                project_id,
                str(pdf_path),
                f"page_{page.page_number}_translated.pdf"
            )
        
        # Extract text from results
        ocr_text = results.get('steps', {}).get('ocr_extraction', {}).get('preview', '')
        translated_text = results.get('steps', {}).get('translation', {}).get('preview', '')
        
        # Update page in database
        page.status = 'completed'
        page.ocr_text = ocr_text
        page.translated_text = translated_text
        page.output_pdf_path = output_pdf_path
        page.processed_at = datetime.utcnow()
        
        # Update project completed count
        project.completed_pages = db.query(Page).filter(
            Page.project_id == project_id,
            Page.status == 'completed'
        ).count()
        
        db.commit()
        
        # Cleanup temp files
        local_path.unlink(missing_ok=True)
        pdf_path.unlink(missing_ok=True)
        
        return {
            'status': 'completed',
            'page_id': page_id,
            'ocr_length': len(ocr_text),
            'translation_length': len(translated_text),
            'pdf_path': output_pdf_path
        }
        
    except Exception as e:
        # Mark page as failed
        page = db.query(Page).filter(Page.id == page_id).first()
        if page:
            page.status = 'failed'
            page.error_message = str(e)
            db.commit()
        
        raise


@celery_app.task(name="process_batch")
def process_batch_task(page_ids: list, project_id: int):
    """Process multiple pages in sequence."""
    results = []
    for page_id in page_ids:
        result = process_page_task.apply_async(args=[page_id, project_id])
        results.append({
            'page_id': page_id,
            'task_id': result.id
        })
    return results
