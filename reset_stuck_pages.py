
import psycopg2

def reset_queued_pages():
    try:
        conn = psycopg2.connect("postgresql://translator:translator123@localhost:5433/book_translator")
        conn.autocommit = True
        cur = conn.cursor()

        print("--- Resetting stuck Page ID 135 to 'UPLOADED' ---")
        cur.execute("UPDATE pages SET status = 'UPLOADED' WHERE id = 135;")
        rows_affected = cur.rowcount
        print(f"✅ Reset {rows_affected} page(s) to 'UPLOADED'.")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    reset_queued_pages()
