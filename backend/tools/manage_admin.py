"""
Script to create or promote a Super Admin user.
Usage: docker exec -it book-translator-backend python3 tools/manage_admin.py --email user@example.com
"""
import sys
import argparse
from pathlib import Path

# Add app directory to path
sys.path.append(str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.db_models import User

def manage_admin(email, promote=True):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"Error: User with email '{email}' not found. Please sign up in the app first.")
            return

        user.is_admin = 1 if promote else 0
        # Admins get unlimited credits by default
        if promote:
            user.total_credits = 999999
            user.subscription_status = "admin"
        
        db.commit()
        status = "promoted to Super Admin" if promote else "demoted to regular user"
        print(f"Success: {email} has been {status}.")
        print(f"Admin privileges: {'Enabled' if user.is_admin else 'Disabled'}")
        print(f"Total Credits: {user.total_credits}")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage admin privileges for users.")
    parser.add_argument("--email", required=True, help="Email of the user to manage")
    parser.add_argument("--demote", action="store_true", help="Demote user instead of promoting")
    
    args = parser.parse_args()
    manage_admin(args.email, promote=not args.demote)
