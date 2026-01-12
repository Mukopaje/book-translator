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

# Add src directory to path for BookTranslator import
project_root = Path(__file__).parent.parent.parent.parent
src_path = Path("/src")

if src_path.exists():
    # In Docker, src is at /src
    sys.path.insert(0, str(src_path))
else:
    # Local development
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
        # Try to find the image locally first (fallback for hybrid storage)
        local_path = storage_service.get_local_path(
            page.original_image_path,
            is_output=False
        )
        
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            image_path = local_path
            logger.info(f"Found image in local storage volume: {image_path}")
        elif settings.use_local_storage:
            # If we are strictly in local mode and it's not there, it's an error
            raise Exception(f"Image not found in local storage: {local_path}")
        else:
            # Try to download from storage service (GCS)
            import tempfile
            import requests
            
            signed_url = storage_service.get_signed_url(
                settings.gcs_bucket_originals,
                page.original_image_path,
                expiration=3600
            )
            
            if signed_url.startswith('file://'):
                image_path = signed_url.replace('file://', '')
            else:
                temp_dir = tempfile.mkdtemp()
                image_path = os.path.join(temp_dir, f"page_{page_id}.jpg")
                
                logger.info(f"Downloading image from Cloud Storage: {signed_url}")
                response = requests.get(signed_url)
                if response.status_code != 200:
                    raise Exception(f"Failed to download from Cloud Storage (404 likely means the file was only uploaded locally): {response.status_code}")
                
                with open(image_path, 'wb') as f:
                    f.write(response.content)
        
        # Import BookTranslator
        from main import BookTranslator
        
        # Process the page
        if not os.path.exists(image_path):
            raise Exception(f"Image file not found at {image_path}")
        
        if os.path.getsize(image_path) == 0:
            raise Exception(f"Image file is empty at {image_path}")

        output_dir = str(project_root / "output")
        os.makedirs(output_dir, exist_ok=True)

        # Get language settings from project
        source_lang = project.source_language or 'auto'
        target_lang = project.target_language or 'en'

        translator = BookTranslator(
            image_path,
            output_dir,
            book_context=project.book_context or '',
            source_language=source_lang,
            target_language=target_lang
        )

        results = translator.process_page(verbose=True)

        # Store detected language at page level
        if results.get('detected_language'):
            page.detected_language = results['detected_language']
            page.language_confidence = results.get('detection_confidence')
            logger.info(f"Detected language for page {page_id}: {page.detected_language} ({page.language_confidence})")

        # Update project-level detection on first successful detection
        if source_lang == 'auto' and results.get('detected_language') and not project.source_language_detected:
            project.source_language_detected = results['detected_language']
            project.source_language_confidence = results.get('detection_confidence')
            logger.info(f"Set project language detection: {project.source_language_detected}")

        if results.get('success'):
            # NEW: Run quality verification
            from agents.quality_agent import QualityVerificationAgent
            import json

            logger.info(f"Running quality verification for page {page_id}...")
            quality_agent = QualityVerificationAgent()

            # Get artifact details for verification
            artifact_details = results.get('steps', {}).get('artifact_details', {})

            # Extract results - try to get OCR and translation text
            ocr_text = results.get('steps', {}).get('ocr_extraction', {}).get('preview', '')
            trans_text = results.get('steps', {}).get('translation', {}).get('preview', '')
            
            # If OCR/translation preview not available, try to read from saved files
            stem = Path(image_path).stem
            if not ocr_text:
                japanese_file = os.path.join(output_dir, f"{stem}_japanese.txt")
                if os.path.exists(japanese_file):
                    with open(japanese_file, 'r', encoding='utf-8') as f:
                        ocr_text = f.read()[:500]  # First 500 chars as preview
            
            if not trans_text:
                translation_file = os.path.join(output_dir, f"{stem}_translation.txt")
                if os.path.exists(translation_file):
                    with open(translation_file, 'r', encoding='utf-8') as f:
                        trans_text = f.read()[:500]  # First 500 chars as preview
            
            # Get PDF path
            pdf_path = os.path.join(output_dir, f"{stem}_translated.pdf")

            # Run quality verification before marking as complete
            try:
                quality_result = quality_agent.verify_page_quality(
                    input_image_path=image_path,
                    output_pdf_path=pdf_path,
                    artifacts=artifact_details,
                    original_ocr_text=ocr_text,
                    translated_text=trans_text,
                    processing_results=results
                )

                # Store quality metrics
                page.quality_score = quality_result['score']
                page.quality_level = quality_result['quality_level']
                page.quality_issues = json.dumps(quality_result['issues'], ensure_ascii=False)
                page.quality_recommendations = json.dumps(quality_result['recommendations'], ensure_ascii=False)

                logger.info(f"Quality verification complete: Score={quality_result['score']}, Level={quality_result['quality_level']}")

                # Log issues if any
                if quality_result['issues']:
                    logger.warning(f"Found {len(quality_result['issues'])} quality issues")
                    for issue in quality_result['issues']:
                        logger.warning(f"  - [{issue['severity']}] {issue['message']}")

            except Exception as qe:
                logger.error(f"Quality verification failed: {qe}")
                # Don't fail the whole task if quality check fails
                page.quality_score = None
                page.quality_level = "Unknown"

            if not os.path.exists(pdf_path):
                error_msg = f"PDF not created at expected path: {pdf_path}"
                logger.error(error_msg)
                # Check if PDF creation step had errors
                pdf_step = results.get('steps', {}).get('pdf_creation', {})
                if not pdf_step.get('success'):
                    error_msg = f"PDF creation failed: {pdf_step.get('error', 'Unknown PDF creation error')}"
                raise FileNotFoundError(error_msg)
            
            # Check for warnings that might indicate issues
            warnings = results.get('warnings', [])
            if warnings:
                logger.warning(f"Page {page_id} completed with warnings: {warnings}")
            
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
                    if not settings.use_local_storage:
                        storage_service.upload_artifacts_json(
                            artifact_json_path,
                            project_id,
                            page.page_number,
                        )
            except Exception as e:
                logger.warning(f"Failed to persist artifacts JSON for page {page_id}: {e}")
            
            # Update page in database
            # Set status based on quality score
            if page.quality_score is not None and page.quality_score < 70:
                page.status = PageStatus.NEEDS_REVIEW
                logger.warning(f"Page {page_id} marked as NEEDS_REVIEW (quality score: {page.quality_score})")
            else:
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
                'ocr_chars': len(ocr_text) if ocr_text else 0,
                'trans_chars': len(trans_text) if trans_text else 0
            }
        else:
            # Processing failed - extract detailed error information
            error_msg = results.get('error', 'Unknown error')
            
            # Try to get more specific error from steps
            if error_msg == 'Unknown error':
                pdf_step = results.get('steps', {}).get('pdf_creation', {})
                if not pdf_step.get('success'):
                    error_msg = pdf_step.get('error', 'PDF creation failed')
                
                # Check for other step errors
                for step_name, step_data in results.get('steps', {}).items():
                    if isinstance(step_data, dict) and not step_data.get('success', True):
                        step_error = step_data.get('error', f'{step_name} failed')
                        error_msg = f"{error_msg}. {step_error}" if error_msg != 'Unknown error' else step_error
                
                # Check warnings that might explain the failure
                warnings = results.get('warnings', [])
                if warnings and error_msg == 'Unknown error':
                    error_msg = f"Processing failed: {'; '.join(warnings[:3])}"  # First 3 warnings
            
            # Log full results for debugging
            logger.error(f"❌ Page {page_id} failed: {error_msg}")
            logger.debug(f"Full results structure: {results}")
            
            page.status = PageStatus.FAILED
            page.error_message = error_msg[:500]  # Limit error message length
            db.commit()
            
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
