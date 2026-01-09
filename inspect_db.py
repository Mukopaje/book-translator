
import psycopg2
# from app.config import settings

def inspect_enums():
    try:
        # Connect to your database
        # Assuming settings.database_url is available or constructing it manually
        # The previous setup_database.py printed: postgresql://translator:translator123@localhost:5432/book_translator
        conn = psycopg2.connect("postgresql://translator:translator123@localhost:5432/book_translator")
        cur = conn.cursor()

        print("--- Inspecting Enum Types ---")
        cur.execute("""
            SELECT t.typname, e.enumlabel
            FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname IN ('pagestatus', 'projectstatus')
            ORDER BY t.typname, e.enumlabel;
        """)
        rows = cur.fetchall()
        for row in rows:
            print(f"Type: {row[0]}, Label: {row[1]}")

        print("\n--- Inspecting Column Types ---")
        cur.execute("""
            SELECT table_name, column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_name IN ('pages', 'projects') AND column_name = 'status';
        """)
        rows = cur.fetchall()
        for row in rows:
            print(f"Table: {row[0]}, Column: {row[1]}, Type: {row[2]}, UDT: {row[3]}")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_enums()
