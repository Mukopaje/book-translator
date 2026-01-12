#!/usr/bin/env python3
"""
Retrigger stuck pages that are in QUEUED status but not actually queued in Celery.
This script finds pages stuck in QUEUED status and resubmits them to the Celery queue.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.db_models import Page, PageStatus, Project
from app.tasks.translation import process_page_task
import os

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://translator:translator_pass@localhost:5433/book_translator')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def main():
    db = SessionLocal()

    try:
        # Find all pages stuck in QUEUED status
        stuck_pages = db.query(Page).filter(Page.status == PageStatus.QUEUED).all()

        if not stuck_pages:
            print("✅ No stuck pages found!")
            return

        print(f"Found {len(stuck_pages)} pages stuck in QUEUED status")
        print("Re-queueing them to Celery...")

        queued_count = 0
        for page in stuck_pages:
            try:
                # Get project for the page
                project = db.query(Project).filter(Project.id == page.project_id).first()

                if not project:
                    print(f"⚠️  Page {page.id} has no project, skipping")
                    continue

                # Queue the page task
                task = process_page_task.apply_async(
                    args=[page.id, page.project_id],
                    queue='celery'
                )

                queued_count += 1
                print(f"  ✅ Page {page.id} (page #{page.page_number}) queued - Task ID: {task.id}")

            except Exception as e:
                print(f"  ❌ Failed to queue page {page.id}: {e}")

        print(f"\n✅ Successfully re-queued {queued_count}/{len(stuck_pages)} pages!")
        print("The worker should now pick them up and start processing.")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
