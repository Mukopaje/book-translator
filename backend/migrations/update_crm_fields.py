"""
Migration: Add Advanced Billing Fields for CRM workflow
"""
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.database import engine, Base
from sqlalchemy import text

def migrate():
    print("Running migration: Add advanced billing fields...")
    
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE billing_documents ADD COLUMN IF NOT EXISTS tax_rate FLOAT DEFAULT 0.0"))
            conn.execute(text("ALTER TABLE billing_documents ADD COLUMN IF NOT EXISTS discount_rate FLOAT DEFAULT 0.0"))
            conn.execute(text("ALTER TABLE billing_documents ADD COLUMN IF NOT EXISTS notes TEXT"))
            conn.execute(text("ALTER TABLE billing_documents ADD COLUMN IF NOT EXISTS due_date TIMESTAMP WITH TIME ZONE"))
            conn.execute(text("ALTER TABLE billing_documents ADD COLUMN IF NOT EXISTS expiry_date TIMESTAMP WITH TIME ZONE"))
            conn.commit()
            print("Successfully updated billing_documents table.")
        except Exception as e:
            print(f"Migration error: {e}")
            conn.rollback()

if __name__ == "__main__":
    migrate()
