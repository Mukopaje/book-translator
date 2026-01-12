"""
Database migration to add quality verification fields to pages table.
Run this script to update existing database schema.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import engine
from app.models.db_models import Base, PageStatus


def upgrade():
    """Add quality verification columns to pages table."""
    print("Starting migration: Adding quality verification fields...")

    with engine.connect() as connection:
        # Start transaction
        trans = connection.begin()

        try:
            # Add new PageStatus enum value
            print("  1. Adding NEEDS_REVIEW to PageStatus enum...")
            connection.execute(text("""
                ALTER TYPE pagestatus ADD VALUE IF NOT EXISTS 'NEEDS_REVIEW';
            """))

            # Add quality_score column
            print("  2. Adding quality_score column...")
            connection.execute(text("""
                ALTER TABLE pages
                ADD COLUMN IF NOT EXISTS quality_score INTEGER NULL;
            """))

            # Add quality_level column
            print("  3. Adding quality_level column...")
            connection.execute(text("""
                ALTER TABLE pages
                ADD COLUMN IF NOT EXISTS quality_level VARCHAR(50) NULL;
            """))

            # Add quality_issues column
            print("  4. Adding quality_issues column...")
            connection.execute(text("""
                ALTER TABLE pages
                ADD COLUMN IF NOT EXISTS quality_issues TEXT NULL;
            """))

            # Add quality_recommendations column
            print("  5. Adding quality_recommendations column...")
            connection.execute(text("""
                ALTER TABLE pages
                ADD COLUMN IF NOT EXISTS quality_recommendations TEXT NULL;
            """))

            # Add replaced_at column
            print("  6. Adding replaced_at column...")
            connection.execute(text("""
                ALTER TABLE pages
                ADD COLUMN IF NOT EXISTS replaced_at TIMESTAMP WITH TIME ZONE NULL;
            """))

            # Commit transaction
            trans.commit()
            print("✅ Migration completed successfully!")

        except Exception as e:
            trans.rollback()
            print(f"❌ Migration failed: {e}")
            raise


def downgrade():
    """Remove quality verification columns (for rollback)."""
    print("Starting rollback: Removing quality verification fields...")

    with engine.connect() as connection:
        trans = connection.begin()

        try:
            print("  1. Removing quality columns...")
            connection.execute(text("""
                ALTER TABLE pages
                DROP COLUMN IF EXISTS quality_score,
                DROP COLUMN IF EXISTS quality_level,
                DROP COLUMN IF EXISTS quality_issues,
                DROP COLUMN IF EXISTS quality_recommendations,
                DROP COLUMN IF EXISTS replaced_at;
            """))

            trans.commit()
            print("✅ Rollback completed successfully!")

        except Exception as e:
            trans.rollback()
            print(f"❌ Rollback failed: {e}")
            raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Database migration for quality fields")
    parser.add_argument(
        "--downgrade",
        action="store_true",
        help="Rollback the migration (remove columns)"
    )

    args = parser.parse_args()

    if args.downgrade:
        downgrade()
    else:
        upgrade()
