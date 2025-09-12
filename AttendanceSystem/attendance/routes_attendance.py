from flask import Blueprint, render_template, request, redirect, url_for, session
import sqlite3
import datetime
import face_recognition
import cv2
import os

attendance_bp = Blueprint("attendance", __name__, url_prefix="/attendance")

DB_PATH = "attendance.db"
KNOWN_FACES_DIR = "attendance/known_faces"


def get_db_conn():
    return sqlite3.connect(DB_PATH)


# ---------- ROUTES ----------

@attendance_bp.route("/")
def home():
    if "admin" not in session:
        return redirect(url_for("admin.login"))
    return """
    <h2>Attendance Module</h2>
    <ul>
      <li><a href="/attendance/scan">Mark Attendance (Face Scan)</a></li>
      <li><a href="/attendance/logs">View Attendance Logs</a></li>
    </ul>
    """


@attendance_bp.route("/scan", methods=["GET"])
def scan_attendance():
    """
    Uses webcam to recognize faces and mark attendance in DB
    """
    if "admin" not in session:
        return redirect(url_for("admin.login"))

    conn = get_db_conn()
    c = conn.cursor()

    # Load known faces
    known_encodings = []
    known_names = []
    for file in os.listdir(KNOWN_FACES_DIR):
        if file.endswith(".jpg") or file.endswith(".png"):
            image = face_recognition.load_image_file(os.path.join(KNOWN_FACES_DIR, file))
            enc = face_recognition.face_encodings(image)[0]
            known_encodings.append(enc)
            known_names.append(os.path.splitext(file)[0])  # filename = student name

    # Start webcam
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    if not ret:
        return "Camera not accessible"

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_frame)
    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

    marked = []
    for face_encoding in face_encodings:
        matches = face_recognition.compare_faces(known_encodings, face_encoding)
        if True in matches:
            idx = matches.index(True)
            name = known_names[idx]

            # mark attendance
            now = datetime.datetime.now()
            c.execute("INSERT INTO attendance (student_name, timestamp) VALUES (?, ?)",
                      (name, now.strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            marked.append(name)

    cap.release()

    return f"Attendance marked for: {', '.join(marked) if marked else 'No known faces detected'}"


@attendance_bp.route("/logs")
def view_logs():
    if "admin" not in session:
        return redirect(url_for("admin.login"))

    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT student_name, timestamp FROM attendance ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()

    html = "<h2>Attendance Logs</h2><ul>"
    for r in rows:
        html += f"<li>{r[0]} — {r[1]}</li>"
    html += "</ul>"
    return html

@attendance_bp.route("/register", methods=["GET", "POST"])
def register_student():
    if "admin" not in session:
        return redirect(url_for("admin.login"))

    if request.method == "POST":
        name = request.form["name"].strip()

        # Start webcam
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        if not ret:
            return "Camera not accessible"

        # Save captured face as image
        save_path = os.path.join(KNOWN_FACES_DIR, f"{name}.jpg")
        cv2.imwrite(save_path, frame)
        cap.release()

        return f"✅ Student {name} registered successfully!"

    return """
    <h2>Register New Student</h2>
    <form method="POST">
        Name: <input type="text" name="name" required>
        <button type="submit">Capture Face</button>
    </form>
    """
