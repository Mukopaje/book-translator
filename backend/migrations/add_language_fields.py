"""
Database migration to add language detection and selection fields.
Run this script to update existing database schema.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import engine


def upgrade():
    """Add language fields to projects and pages tables."""
    print("Starting migration: Adding language fields...")

    with engine.connect() as connection:
        # Start transaction
        trans = connection.begin()

        try:
            # Add language fields to projects table
            print("  1. Adding source_language to projects...")
            connection.execute(text("""
                ALTER TABLE projects
                ADD COLUMN IF NOT EXISTS source_language VARCHAR(10) DEFAULT 'auto';
            """))

            print("  2. Adding source_language_detected to projects...")
            connection.execute(text("""
                ALTER TABLE projects
                ADD COLUMN IF NOT EXISTS source_language_detected VARCHAR(10);
            """))

            print("  3. Adding source_language_confidence to projects...")
            connection.execute(text("""
                ALTER TABLE projects
                ADD COLUMN IF NOT EXISTS source_language_confidence FLOAT;
            """))

            print("  4. Updating target_language column...")
            # Note: This column already exists but ensure it has proper default
            connection.execute(text("""
                ALTER TABLE projects
                ALTER COLUMN target_language SET DEFAULT 'en';
            """))

            # Add language detection results to pages table
            print("  5. Adding detected_language to pages...")
            connection.execute(text("""
                ALTER TABLE pages
                ADD COLUMN IF NOT EXISTS detected_language VARCHAR(10);
            """))

            print("  6. Adding language_confidence to pages...")
            connection.execute(text("""
                ALTER TABLE pages
                ADD COLUMN IF NOT EXISTS language_confidence FLOAT;
            """))

            # Commit transaction
            trans.commit()
            print("✅ Migration completed successfully!")
            print("\nAdded fields:")
            print("  Projects:")
            print("    - source_language (VARCHAR(10), default 'auto')")
            print("    - source_language_detected (VARCHAR(10))")
            print("    - source_language_confidence (FLOAT)")
            print("  Pages:")
            print("    - detected_language (VARCHAR(10))")
            print("    - language_confidence (FLOAT)")

        except Exception as e:
            trans.rollback()
            print(f"❌ Migration failed: {e}")
            raise


def downgrade():
    """Remove language fields (for rollback)."""
    print("Starting rollback: Removing language fields...")

    with engine.connect() as connection:
        trans = connection.begin()

        try:
            print("  1. Removing language columns from projects...")
            connection.execute(text("""
                ALTER TABLE projects
                DROP COLUMN IF EXISTS source_language,
                DROP COLUMN IF EXISTS source_language_detected,
                DROP COLUMN IF EXISTS source_language_confidence;
            """))

            print("  2. Removing language columns from pages...")
            connection.execute(text("""
                ALTER TABLE pages
                DROP COLUMN IF EXISTS detected_language,
                DROP COLUMN IF EXISTS language_confidence;
            """))

            trans.commit()
            print("✅ Rollback completed successfully!")

        except Exception as e:
            trans.rollback()
            print(f"❌ Rollback failed: {e}")
            raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Database migration for language fields")
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
