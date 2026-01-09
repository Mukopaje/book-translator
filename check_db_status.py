
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv("backend/.env")

def check_page_status():
    try:
        # Connect to your postgres DB
        conn = psycopg2.connect("postgresql://translator:translator123@localhost:5432/book_translator")
        cur = conn.cursor()

        cur.execute("SELECT id, page_number, status FROM pages ORDER BY page_number;")
        rows = cur.fetchall()

        print(f"{'ID':<5} {'Page #':<8} {'Status':<15}")
        print("-" * 30)
        for row in rows:
            print(f"{row[0]:<5} {row[1]:<8} {row[2]:<15}")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_page_status()
