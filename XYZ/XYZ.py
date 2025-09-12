"""
Automated Attendance System - Single-file Prototype (Flask)
---------------------------------------------------------
How to use:
 1. Create a virtualenv and install dependencies:
      python -m venv venv
      venv\Scripts\activate   # Windows
      source venv/bin/activate  # macOS / Linux
      pip install flask face_recognition opencv-python numpy

 2. Run:
      python Attendance_Web_Prototype.py

 3. Open in browser:
      http://127.0.0.1:5000/        -> Attendance (camera) page
      http://127.0.0.1:5000/admin/login -> Admin login

Notes / Limitations:
 - This is a prototype for demo and development only. Do NOT deploy to production without:
     * HTTPS, hardened auth, input validation, rate-limits
     * Proper handling of face data privacy & consent
 - face_recognition depends on dlib and CMake; install system deps first if building from source.

"""

from flask import Flask, request, render_template_string, redirect, url_for, session, send_file, Response
import sqlite3
import os
import io
import base64
import pickle
from datetime import datetime
import face_recognition
import numpy as np
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import csv

DB_PATH = 'attendance.db'
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXT = {'png', 'jpg', 'jpeg'}
ADMIN_USERNAME = 'admin'
# change this default password ASAP
ADMIN_DEFAULT_PASSWORD = 'admin'

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------- Database helpers ----------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    roll TEXT NOT NULL,
                    encoding BLOB NOT NULL
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
    # ensure admin exists
    c.execute('SELECT * FROM admin WHERE username = ?', (ADMIN_USERNAME,))
    if not c.fetchone():
        pw_hash = generate_password_hash(ADMIN_DEFAULT_PASSWORD)
        c.execute('INSERT INTO admin (username, password_hash) VALUES (?, ?)', (ADMIN_USERNAME, pw_hash))
    conn.commit()
    conn.close()


def get_db_conn():
    return sqlite3.connect(DB_PATH)


# ---------- Utility helpers ----------

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def save_encoding(name, roll, encoding):
    data = pickle.dumps(encoding)
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('INSERT INTO users (name, roll, encoding) VALUES (?, ?, ?)', (name, roll, data))
    conn.commit()
    conn.close()


def load_all_encodings():
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT id, name, roll, encoding FROM users')
    rows = c.fetchall()
    conn.close()
    users = []
    for r in rows:
        uid, name, roll, enc_blob = r
        encoding = pickle.loads(enc_blob)
        users.append({'id': uid, 'name': name, 'roll': roll, 'encoding': encoding})
    return users


def mark_attendance(user_id, name, roll):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('INSERT INTO attendance (user_id, name, roll, timestamp) VALUES (?, ?, ?, ?)', (user_id, name, roll, ts))
    conn.commit()
    conn.close()


# ---------- Routes: Frontend (Attendance) ----------

INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Face Attendance - Scan</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>body{font-family:Arial;padding:10px;max-width:720px;margin:auto}button{padding:10px 16px}</style>
</head>
<body>
  <h2>Attendance - Face Scan</h2>
  <video id="video" width="640" height="480" autoplay muted></video>
  <div>
    <button id="snap">Capture & Mark Attendance</button>
    <button id="toggleCam">Turn Off Camera</button>
  </div>
  <p id="status"></p>
  <script>
    let streaming = false;
    const video = document.getElementById('video');
    const status = document.getElementById('status');
    const snap = document.getElementById('snap');
    const toggleCam = document.getElementById('toggleCam');
    let streamRef;

    async function startCam(){
      try{
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        streamRef = stream;
        video.srcObject = stream;
        streaming = true;
      }catch(e){
        status.innerText = 'Camera access denied or not available.';
      }
    }

    startCam();

    toggleCam.onclick = ()=>{
      if(streamRef){
        streamRef.getTracks().forEach(t=>t.stop());
        streamRef = null;
        status.innerText = 'Camera stopped.';
      } else startCam();
    }

    snap.onclick = async ()=>{
      if(!streamRef){ status.innerText='Camera not available'; return }
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(async (blob)=>{
        status.innerText = 'Sending image to server...';
        const form = new FormData();
        form.append('image', blob, 'capture.jpg');
        const resp = await fetch('/mark_attendance', { method: 'POST', body: form });
        const data = await resp.json();
        if(data.success){
          status.innerText = `Marked: ${data.name} (Roll: ${data.roll}) at ${data.timestamp}`;
        } else {
          status.innerText = `No match found`;
        }
      }, 'image/jpeg', 0.9);
    }
  </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(INDEX_HTML)


@app.route('/mark_attendance', methods=['POST'])
def mark_attendance_route():
    if 'image' not in request.files:
        return {'success': False, 'error': 'no image'}, 400
    file = request.files['image']
    if file.filename == '':
        return {'success': False, 'error': 'empty filename'}, 400
    img_bytes = file.read()
    npimg = np.frombuffer(img_bytes, np.uint8)
    import cv2
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
    # convert to RGB
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb)
    if not face_locations:
        return {'success': False, 'error': 'no face detected'}
    face_encodings = face_recognition.face_encodings(rgb, face_locations)
    users = load_all_encodings()
    known_encodings = [u['encoding'] for u in users]
    names = [u['name'] for u in users]
    rolls = [u['roll'] for u in users]
    ids = [u['id'] for u in users]
    for enc in face_encodings:
        if len(known_encodings) == 0:
            continue
        results = face_recognition.compare_faces(known_encodings, enc, tolerance=0.45)
        face_dist = face_recognition.face_distance(known_encodings, enc)
        # pick best match
        best_idx = np.argmin(face_dist)
        if results[best_idx]:
            user_id = ids[best_idx]
            user_name = names[best_idx]
            user_roll = rolls[best_idx]
            mark_attendance(user_id, user_name, user_roll)
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            return {'success': True, 'name': user_name, 'roll': user_roll, 'timestamp': ts}
    return {'success': False}


# ---------- Admin UI and APIs ----------

LOGIN_HTML = """
<!doctype html>
<title>Admin Login</title>
<h2>Admin Login</h2>
<form method="post" action="{{ url_for('admin_login') }}">
  <label>Username: <input name="username"></label><br>
  <label>Password: <input type="password" name="password"></label><br>
  <input type="submit" value="Login">
</form>
"""


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'GET':
        return render_template_string(LOGIN_HTML)
    username = request.form.get('username')
    password = request.form.get('password')
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT password_hash FROM admin WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    if row and check_password_hash(row[0], password):
        session['admin'] = username
        return redirect(url_for('admin_dashboard'))
    return 'Login failed', 401


DASH_HTML = """
<!doctype html>
<title>Admin Dashboard</title>
<h2>Admin Dashboard</h2>
<p><a href="{{ url_for('admin_logout') }}">Logout</a></p>
<ul>
  <li><a href="{{ url_for('admin_register') }}">Register new student</a></li>
  <li><a href="{{ url_for('admin_view_attendance') }}">View attendance</a></li>
  <li><a href="{{ url_for('admin_list_students') }}">List students</a></li>
</ul>
"""


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))


@app.route('/admin')
def admin_dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    return render_template_string(DASH_HTML)


REGISTER_HTML = """
<!doctype html>
<title>Register Student</title>
<h2>Register Student</h2>
<form method="post" action="{{ url_for('admin_register') }}" enctype="multipart/form-data">
  <label>Name: <input name="name" required></label><br>
  <label>Roll: <input name="roll" required></label><br>
  <label>Face Image: <input type="file" name="image" accept="image/*" required></label><br>
  <input type="submit" value="Register">
</form>
<p><a href="{{ url_for('admin_dashboard') }}">Back</a></p>
"""


@app.route('/admin/register', methods=['GET', 'POST'])
def admin_register():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    if request.method == 'GET':
        return render_template_string(REGISTER_HTML)
    name = request.form.get('name')
    roll = request.form.get('roll')
    file = request.files.get('image')
    if not file or file.filename == '':
        return 'Image required', 400
    if not allowed_file(file.filename):
        return 'Invalid file type', 400
    filename = secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(path)
    # load and compute encoding
    img = face_recognition.load_image_file(path)
    locs = face_recognition.face_locations(img)
    if not locs:
        return 'No face detected in image', 400
    enc = face_recognition.face_encodings(img, locs)[0]
    save_encoding(name, roll, enc)
    return redirect(url_for('admin_list_students'))


LIST_STU_HTML = """
<!doctype html>
<title>Students</title>
<h2>Registered Students</h2>
<table border=1 cellpadding=6>
<tr><th>ID</th><th>Name</th><th>Roll</th></tr>
{% for s in students %}
<tr><td>{{ s[0] }}</td><td>{{ s[1] }}</td><td>{{ s[2] }}</td></tr>
{% endfor %}
</table>
<p><a href="{{ url_for('admin_dashboard') }}">Back</a></p>
"""


@app.route('/admin/students')
def admin_list_students():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT id, name, roll FROM users')
    students = c.fetchall()
    conn.close()
    return render_template_string(LIST_STU_HTML, students=students)


ATT_VIEW_HTML = """
<!doctype html>
<title>Attendance Records</title>
<h2>Attendance</h2>
<form method="get">
  Filter date (YYYY-mm-dd): <input name="date" value="{{ req_date }}"> <input type="submit" value="Filter">
</form>
<p><a href="{{ url_for('export_csv', date=req_date) }}">Export CSV</a></p>
<table border=1 cellpadding=6>
<tr><th>ID</th><th>Name</th><th>Roll</th><th>Timestamp</th></tr>
{% for a in records %}
<tr><td>{{ a[0] }}</td><td>{{ a[1] }}</td><td>{{ a[2] }}</td><td>{{ a[3] }}</td></tr>
{% endfor %}
</table>
<p><a href="{{ url_for('admin_dashboard') }}">Back</a></p>
"""


@app.route('/admin/attendance')
def admin_view_attendance():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    req_date = request.args.get('date', '')
    conn = get_db_conn()
    c = conn.cursor()
    if req_date:
        like = req_date + '%'
        c.execute('SELECT id, name, roll, timestamp FROM attendance WHERE timestamp LIKE ? ORDER BY timestamp DESC', (like,))
    else:
        c.execute('SELECT id, name, roll, timestamp FROM attendance ORDER BY timestamp DESC LIMIT 100')
    records = c.fetchall()
    conn.close()
    return render_template_string(ATT_VIEW_HTML, records=records, req_date=req_date)


@app.route('/admin/export')
def export_csv():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    req_date = request.args.get('date', '')
    conn = get_db_conn()
    c = conn.cursor()
    if req_date:
        like = req_date + '%'
        c.execute('SELECT id, name, roll, timestamp FROM attendance WHERE timestamp LIKE ? ORDER BY timestamp DESC', (like,))
    else:
        c.execute('SELECT id, name, roll, timestamp FROM attendance ORDER BY timestamp DESC')
    rows = c.fetchall()
    conn.close()
    # create CSV in-memory
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['id', 'name', 'roll', 'timestamp'])
    cw.writerows(rows)
    mem = io.BytesIO()
    mem.write(si.getvalue().encode('utf-8'))
    mem.seek(0)
    fname = 'attendance_export.csv'
    return send_file(mem, as_attachment=True, download_name=fname, mimetype='text/csv')


# ---------- Run ----------

if __name__ == '__main__':
    init_db()
    print('Starting server. Admin user:', ADMIN_USERNAME, 'default password:', ADMIN_DEFAULT_PASSWORD)
    app.run(debug=True)
