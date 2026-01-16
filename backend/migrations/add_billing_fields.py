"""
Migration: Add Billing and Admin Fields to User Table
"""
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.database import engine, Base
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, Float, text

def migrate():
    print("Running migration: Add billing and admin fields to users...")
    
    with engine.connect() as conn:
        # PostgreSQL syntax for adding columns
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS total_credits INTEGER DEFAULT 5"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS used_credits INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255)"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(50) DEFAULT 'free'"))
            conn.commit()
            print("Successfully updated users table.")
        except Exception as e:
            print(f"Migration error: {e}")
            conn.rollback()

if __name__ == "__main__":
    migrate()
