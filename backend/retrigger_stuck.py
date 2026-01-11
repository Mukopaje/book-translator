import sys
import os
import time

# Add /src to path if it exists (for worker context)
if os.path.exists("/src"):
    sys.path.insert(0, "/src")

from app.database import SessionLocal
from app.models.db_models import Page, PageStatus, Project
from app.tasks.translation import process_page_task
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def retrigger_stuck_pages():
    db = SessionLocal()
    try:
        # Find pages with status UPLOADED or QUEUED
        # Since queue is confirmed empty (via redis-cli), QUEUED pages are stuck.
        pages = db.query(Page).filter(Page.status.in_([PageStatus.UPLOADED, PageStatus.QUEUED])).all()
        
        if not pages:
            logger.info("No pages found with status UPLOADED or QUEUED.")
            return

        logger.info(f"Found {len(pages)} pages with status UPLOADED or QUEUED.")
        
        for page in pages:
            logger.info(f"Retriggering processing for Page ID: {page.id} (Page #{page.page_number}) in Project ID: {page.project_id} (Status: {page.status})")
            
            # Dispatch task
            process_page_task.delay(page.id, page.project_id)
            
            # Optional: Set to QUEUED to indicate it's been picked up
            # page.status = PageStatus.QUEUED
            # db.commit()
            
    except Exception as e:
        logger.error(f"Error retriggering pages: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    retrigger_stuck_pages()
