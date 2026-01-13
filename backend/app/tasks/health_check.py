"""
Health Check Tasks
Automatically detect and recover stuck pages to prevent system lockups.
"""
from celery import shared_task
from datetime import datetime, timedelta, timezone
from app.database import SessionLocal
from app.models.db_models import Page, PageStatus
import logging

logger = logging.getLogger(__name__)


@shared_task(name="app.tasks.health_check.recover_stuck_pages")
def recover_stuck_pages():
    """
    Detect and recover pages stuck in PROCESSING or QUEUED status.

    A page is considered stuck if:
    - Status is PROCESSING for more than 30 minutes
    - Status is QUEUED for more than 10 minutes (should be picked up quickly)

    Recovery action: Reset to UPLOADED with error message explaining the issue.
    """
    db = SessionLocal()

    try:
        # Use timezone-aware datetime to match database timestamps
        now = datetime.now(timezone.utc)

        # Define timeout thresholds
        processing_timeout = now - timedelta(minutes=30)
        queued_timeout = now - timedelta(minutes=10)

        # Find stuck PROCESSING pages
        stuck_processing = db.query(Page).filter(
            Page.status == PageStatus.PROCESSING,
            Page.updated_at < processing_timeout
        ).all()

        # Find stuck QUEUED pages
        stuck_queued = db.query(Page).filter(
            Page.status == PageStatus.QUEUED,
            Page.updated_at < queued_timeout
        ).all()

        total_recovered = 0

        # Recover stuck PROCESSING pages
        for page in stuck_processing:
            age_minutes = (now - page.updated_at).total_seconds() / 60
            logger.warning(
                f"Recovering stuck PROCESSING page {page.id} "
                f"(page #{page.page_number}, stuck for {age_minutes:.1f} minutes)"
            )
            page.status = PageStatus.UPLOADED
            page.error_message = (
                f"Automatically recovered from stuck PROCESSING status "
                f"(stuck for {age_minutes:.1f} minutes). Ready to retry."
            )
            total_recovered += 1

        # Recover stuck QUEUED pages
        for page in stuck_queued:
            age_minutes = (now - page.updated_at).total_seconds() / 60
            logger.warning(
                f"Recovering stuck QUEUED page {page.id} "
                f"(page #{page.page_number}, stuck for {age_minutes:.1f} minutes)"
            )
            page.status = PageStatus.UPLOADED
            page.error_message = (
                f"Automatically recovered from stuck QUEUED status "
                f"(stuck for {age_minutes:.1f} minutes). Ready to retry."
            )
            total_recovered += 1

        if total_recovered > 0:
            db.commit()
            logger.info(f"✅ Recovered {total_recovered} stuck pages")
        else:
            logger.debug("No stuck pages found")

        return {
            "success": True,
            "recovered": total_recovered,
            "processing": len(stuck_processing),
            "queued": len(stuck_queued)
        }

    except Exception as e:
        logger.error(f"Error during health check: {e}")
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task(name="app.tasks.health_check.cleanup_old_errors")
def cleanup_old_errors():
    """
    Optional: Clear error messages from pages that have been FAILED for a long time.
    This keeps the database clean and helps identify fresh issues.
    """
    db = SessionLocal()

    try:
        # Clear error messages from FAILED pages older than 7 days
        old_threshold = datetime.now(timezone.utc) - timedelta(days=7)

        old_failed = db.query(Page).filter(
            Page.status == PageStatus.FAILED,
            Page.updated_at < old_threshold,
            Page.error_message.isnot(None)
        ).all()

        count = 0
        for page in old_failed:
            # Archive error message but keep status
            page.error_message = f"[Archived] {page.error_message[:100]}..."
            count += 1

        if count > 0:
            db.commit()
            logger.info(f"Archived {count} old error messages")

        return {"success": True, "archived": count}

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()
