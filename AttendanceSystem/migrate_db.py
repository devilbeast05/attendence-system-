import sqlite3
import os

# Use absolute path for database to ensure persistence
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "instance", "attendance.db"))

def migrate_db():
    print(f"Migrating database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if synced column exists in students table
    cursor.execute("PRAGMA table_info(students)")
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]
    
    if 'synced' not in column_names:
        print("Adding 'synced' column to students table...")
        cursor.execute("ALTER TABLE students ADD COLUMN synced INTEGER DEFAULT 0")
        print("Column added successfully.")
    else:
        print("'synced' column already exists in students table.")
    
    # Check if synced column exists in attendance table
    cursor.execute("PRAGMA table_info(attendance)")
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]
    
    if 'synced' not in column_names:
        print("Adding 'synced' column to attendance table...")
        cursor.execute("ALTER TABLE attendance ADD COLUMN synced INTEGER DEFAULT 0")
        print("Column added successfully.")
    else:
        print("'synced' column already exists in attendance table.")
    
    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate_db()