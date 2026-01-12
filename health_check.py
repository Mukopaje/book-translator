#!/usr/bin/env python3
"""
Manual Health Check Script
Run this script to manually check for and recover stuck pages.

Usage:
    python health_check.py              # Check and recover stuck pages
    python health_check.py --dry-run    # Check only, don't recover
    python health_check.py --status     # Show system status
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from app.models.db_models import Page, PageStatus, Project
import os


def get_db_session():
    """Create database session"""
    DATABASE_URL = os.getenv(
        'DATABASE_URL',
        'postgresql://translator:translator_pass@localhost:5433/book_translator'
    )
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def check_stuck_pages(dry_run=False):
    """Check for and optionally recover stuck pages"""
    db = get_db_session()

    try:
        now = datetime.utcnow()
        processing_timeout = now - timedelta(minutes=30)
        queued_timeout = now - timedelta(minutes=10)

        # Find stuck pages
        stuck_processing = db.query(Page).filter(
            Page.status == PageStatus.PROCESSING,
            Page.updated_at < processing_timeout
        ).all()

        stuck_queued = db.query(Page).filter(
            Page.status == PageStatus.QUEUED,
            Page.updated_at < queued_timeout
        ).all()

        total_stuck = len(stuck_processing) + len(stuck_queued)

        if total_stuck == 0:
            print("✅ No stuck pages found!")
            return 0

        print(f"\n⚠️  Found {total_stuck} stuck pages:")
        print(f"   - PROCESSING (>30 min): {len(stuck_processing)}")
        print(f"   - QUEUED (>10 min): {len(stuck_queued)}")

        if dry_run:
            print("\n🔍 DRY RUN - No changes made\n")
            print("Stuck PROCESSING pages:")
            for page in stuck_processing:
                age_minutes = (now - page.updated_at).total_seconds() / 60
                print(f"  - Page {page.id} (#{page.page_number}): stuck for {age_minutes:.1f} min")

            print("\nStuck QUEUED pages:")
            for page in stuck_queued:
                age_minutes = (now - page.updated_at).total_seconds() / 60
                print(f"  - Page {page.id} (#{page.page_number}): stuck for {age_minutes:.1f} min")

            return total_stuck

        # Recover stuck pages
        print("\n🔧 Recovering stuck pages...\n")

        for page in stuck_processing:
            age_minutes = (now - page.updated_at).total_seconds() / 60
            print(f"  ✓ Page {page.id} (#{page.page_number}): PROCESSING → UPLOADED (stuck {age_minutes:.1f} min)")
            page.status = PageStatus.UPLOADED
            page.error_message = f"Auto-recovered from stuck PROCESSING ({age_minutes:.1f} min)"

        for page in stuck_queued:
            age_minutes = (now - page.updated_at).total_seconds() / 60
            print(f"  ✓ Page {page.id} (#{page.page_number}): QUEUED → UPLOADED (stuck {age_minutes:.1f} min)")
            page.status = PageStatus.UPLOADED
            page.error_message = f"Auto-recovered from stuck QUEUED ({age_minutes:.1f} min)"

        db.commit()
        print(f"\n✅ Successfully recovered {total_stuck} pages!\n")

        return total_stuck

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return -1
    finally:
        db.close()


def show_status():
    """Show overall system status"""
    db = get_db_session()

    try:
        print("\n📊 System Status\n")
        print("=" * 60)

        # Count pages by status
        status_counts = {}
        for status in PageStatus:
            count = db.query(Page).filter(Page.status == status).count()
            status_counts[status.value] = count

        print("\nPage Status Distribution:")
        for status, count in sorted(status_counts.items()):
            emoji = {
                'UPLOADED': '📤',
                'QUEUED': '⏳',
                'PROCESSING': '⚙️',
                'COMPLETED': '✅',
                'FAILED': '❌',
                'NEEDS_REVIEW': '⚠️'
            }.get(status, '📄')
            print(f"  {emoji} {status:15s}: {count:5d}")

        # Check for potentially stuck pages
        now = datetime.utcnow()
        processing_timeout = now - timedelta(minutes=30)
        queued_timeout = now - timedelta(minutes=10)

        stuck_processing = db.query(Page).filter(
            Page.status == PageStatus.PROCESSING,
            Page.updated_at < processing_timeout
        ).count()

        stuck_queued = db.query(Page).filter(
            Page.status == PageStatus.QUEUED,
            Page.updated_at < queued_timeout
        ).count()

        print("\nHealth Check:")
        if stuck_processing == 0 and stuck_queued == 0:
            print("  ✅ All pages healthy (no stuck pages)")
        else:
            print(f"  ⚠️  Stuck pages detected:")
            if stuck_processing > 0:
                print(f"     - {stuck_processing} PROCESSING (>30 min)")
            if stuck_queued > 0:
                print(f"     - {stuck_queued} QUEUED (>10 min)")
            print(f"\n  Run 'python health_check.py' to recover")

        # Project statistics
        total_projects = db.query(Project).count()
        active_projects = db.query(Project).filter(
            Project.status.in_(['PROCESSING', 'ACTIVE'])
        ).count()

        print(f"\nProjects:")
        print(f"  Total: {total_projects}")
        print(f"  Active: {active_projects}")

        print("\n" + "=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Health check and recovery for book translator system"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Check for stuck pages but don't recover them"
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help="Show overall system status"
    )

    args = parser.parse_args()

    if args.status:
        show_status()
    else:
        result = check_stuck_pages(dry_run=args.dry_run)
        sys.exit(0 if result >= 0 else 1)


if __name__ == "__main__":
    main()
