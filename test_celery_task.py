import sys
import os
from pathlib import Path

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.getcwd(), 'backend', '.env'))

from app.celery_app import celery_app
from app.tasks.translation import process_batch_task

def send_test_task():
    print("Sending test task...")
    # We'll send a dummy task with a non-existent project ID to see if it logs an error
    # or at least starts.
    try:
        task = process_batch_task.apply_async(args=[99999, []], queue='translation')
        print(f"Task sent: {task.id}")
    except Exception as e:
        print(f"Error sending task: {e}")

if __name__ == "__main__":
    send_test_task()
