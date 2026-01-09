
import psycopg2

def fix_enum():
    try:
        conn = psycopg2.connect("postgresql://translator:translator123@localhost:5432/book_translator")
        conn.autocommit = True
        cur = conn.cursor()

        print("--- Adding 'QUEUED' to pagestatus Enum ---")
        try:
            cur.execute("ALTER TYPE pagestatus ADD VALUE 'QUEUED';")
            print("✅ Successfully added 'QUEUED' to pagestatus.")
        except psycopg2.errors.DuplicateObject:
            print("⚠️ 'QUEUED' already exists in pagestatus.")
        except Exception as e:
            print(f"❌ Error adding value: {e}")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"Error connecting: {e}")

if __name__ == "__main__":
    fix_enum()
