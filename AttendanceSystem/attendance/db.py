import sqlite3
import pickle
from werkzeug.security import generate_password_hash
import os

# Use absolute path for database to ensure persistence
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "instance", "attendance.db"))
ADMIN_USERNAME = "admin"
ADMIN_DEFAULT_PASSWORD = "admin"

def get_db_conn():
    # Add timeout parameter to wait for database lock to be released
    return sqlite3.connect(DB_PATH, timeout=30)

def init_db():
    os.makedirs("instance", exist_ok=True)
    conn = get_db_conn()
    c = conn.cursor()

    # tables
    c.execute('''CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    roll TEXT,
                    class TEXT,
                    section TEXT,
                    face_encoding BLOB,
                    synced INTEGER DEFAULT 0
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    timestamp TEXT,
                    synced INTEGER DEFAULT 0
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS admin (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password_hash TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sync_timestamp TEXT,
                    records_synced INTEGER
                )''')

    # default admin
    c.execute("SELECT * FROM admin WHERE username=?", (ADMIN_USERNAME,))
    if not c.fetchone():
        pw_hash = generate_password_hash(ADMIN_DEFAULT_PASSWORD)
        c.execute("INSERT INTO admin (username, password_hash) VALUES (?, ?)", (ADMIN_USERNAME, pw_hash))

    conn.commit()
    conn.close()
