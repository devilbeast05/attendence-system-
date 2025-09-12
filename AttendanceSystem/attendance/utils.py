import pickle, os

ALLOWED_EXT = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def save_encoding(conn, name, roll, encoding):
    data = pickle.dumps(encoding)
    c = conn.cursor()
    c.execute("INSERT INTO users (name, roll, encoding) VALUES (?, ?, ?)", (name, roll, data))
    conn.commit()

def load_all_encodings(conn):
    c = conn.cursor()
    c.execute("SELECT id, name, roll, encoding FROM users")
    rows = c.fetchall()
    users = []
    for uid, name, roll, enc_blob in rows:
        users.append({"id": uid, "name": name, "roll": roll, "encoding": pickle.loads(enc_blob)})
    return users
