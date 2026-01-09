"""Setup PostgreSQL database for Book Translator backend."""
import subprocess
import sys
from pathlib import Path

# Common PostgreSQL installation paths
PSQL_PATHS = [
    r"C:\Program Files\PostgreSQL\16\bin\psql.exe",
    r"C:\Program Files\PostgreSQL\15\bin\psql.exe",
    r"C:\Program Files\PostgreSQL\14\bin\psql.exe",
    r"C:\Program Files (x86)\PostgreSQL\16\bin\psql.exe",
    r"C:\PostgreSQL\16\bin\psql.exe",
]

def find_psql():
    """Find psql executable."""
    for path in PSQL_PATHS:
        if Path(path).exists():
            return path
    return None

def run_psql_command(psql_path, command, database="postgres"):
    """Run a psql command."""
    cmd = [
        psql_path,
        "-U", "postgres",
        "-d", database,
        "-c", command
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result

def main():
    print("🔍 Finding PostgreSQL installation...")
    psql_path = find_psql()
    
    if not psql_path:
        print("❌ PostgreSQL not found in standard locations.")
        print("Please install PostgreSQL or provide the path to psql.exe")
        return 1
    
    print(f"✅ Found PostgreSQL at: {psql_path}")
    
    print("\n📊 Creating database 'book_translator'...")
    result = run_psql_command(psql_path, "CREATE DATABASE book_translator;")
    
    if result.returncode == 0 or "already exists" in result.stderr:
        print("✅ Database created (or already exists)")
    else:
        print(f"❌ Error: {result.stderr}")
        return 1
    
    print("\n👤 Creating user 'translator'...")
    result = run_psql_command(
        psql_path,
        "CREATE USER translator WITH PASSWORD 'translator123';",
        database="book_translator"
    )
    
    if result.returncode == 0 or "already exists" in result.stderr:
        print("✅ User created (or already exists)")
    else:
        print(f"⚠️  Warning: {result.stderr}")
    
    print("\n🔐 Granting privileges...")
    result = run_psql_command(
        psql_path,
        "GRANT ALL PRIVILEGES ON DATABASE book_translator TO translator;",
        database="book_translator"
    )
    
    if result.returncode == 0:
        print("✅ Privileges granted")
    else:
        print(f"⚠️  Warning: {result.stderr}")
    
    print("\n✨ Database setup complete!")
    print("\nConnection string:")
    print("postgresql://translator:translator123@localhost:5432/book_translator")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
