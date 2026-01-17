"""
Migration: Add Billing Documents table for CRM functionality
"""
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.database import engine, Base
from sqlalchemy import text

def migrate():
    print("Running migration: Create billing_documents table...")
    
    with engine.connect() as conn:
        try:
            # Create the table if it doesn't exist
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS billing_documents (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    doc_type VARCHAR(20) NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
                    amount FLOAT NOT NULL,
                    currency VARCHAR(10) DEFAULT 'USD',
                    items TEXT,
                    stripe_invoice_id VARCHAR(255),
                    pdf_gcs_path VARCHAR(500),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE,
                    paid_at TIMESTAMP WITH TIME ZONE
                )
            """))
            conn.commit()
            print("Successfully created billing_documents table.")
        except Exception as e:
            print(f"Migration error: {e}")
            conn.rollback()

if __name__ == "__main__":
    migrate()
