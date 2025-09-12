import sqlite3
import pickle
from werkzeug.security import generate_password_hash
import os

DB_PATH = os.path.join("instance", "attendance.db")
ADMIN_USERNAME = "admin"
ADMIN_DEFAULT_PASSWORD = "admin"

def get_db_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    os.makedirs("instance", exist_ok=True)
    conn = get_db_conn()
    c = conn.cursor()

    # tables
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    roll TEXT,
                    encoding BLOB
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    name TEXT,
                    roll TEXT,
                    timestamp TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS admin (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password_hash TEXT
                )''')

    # default admin
    c.execute("SELECT * FROM admin WHERE username=?", (ADMIN_USERNAME,))
    if not c.fetchone():
        pw_hash = generate_password_hash(ADMIN_DEFAULT_PASSWORD)
        c.execute("INSERT INTO admin (username, password_hash) VALUES (?, ?)", (ADMIN_USERNAME, pw_hash))

    conn.commit()
    conn.close()
