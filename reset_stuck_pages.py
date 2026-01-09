
import psycopg2

def reset_queued_pages():
    try:
        conn = psycopg2.connect("postgresql://translator:translator123@localhost:5432/book_translator")
        conn.autocommit = True
        cur = conn.cursor()

        print("--- Resetting stuck 'QUEUED', 'PROCESSING', and 'FAILED' pages to 'UPLOADED' ---")
        cur.execute("UPDATE pages SET status = 'UPLOADED' WHERE status IN ('QUEUED', 'PROCESSING', 'FAILED');")
        rows_affected = cur.rowcount
        print(f"✅ Reset {rows_affected} pages to 'UPLOADED'.")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    reset_queued_pages()
