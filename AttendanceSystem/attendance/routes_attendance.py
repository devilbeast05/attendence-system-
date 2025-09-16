from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3
import datetime
import face_recognition
import cv2
import os
from PIL import Image
import numpy as np
from io import BytesIO
import base64
import re
from werkzeug.utils import secure_filename

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

attendance_bp = Blueprint("attendance", __name__, url_prefix="/attendance")

from .db import DB_PATH
# Update to use absolute path
KNOWN_FACES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "known_faces"))


def get_db_conn():
    return sqlite3.connect(DB_PATH)


# ---------- ROUTES ----------

@attendance_bp.route("/")
def home():
    if "admin" not in session:
        return redirect(url_for("admin.login"))
    return render_template("home.html")


@attendance_bp.route("/scan", methods=["GET", "POST"])
def scan_attendance():
    """
    Uses webcam to recognize faces and mark attendance in DB
    """
    if "admin" not in session:
        return redirect(url_for("admin.login"))

    # For POST requests (from the new UI)
    if request.method == "POST":
        try:
            # Get the image data from JSON
            data = request.get_json()
            if not data or 'image' not in data:
                return jsonify({"success": False, "message": "No image data provided"})
            
            # Process the base64 image
            import base64
            import numpy as np
            import re
            
            # Extract the base64 encoded image data
            image_data = data['image']
            image_data = re.sub('^data:image/.+;base64,', '', image_data)
            image_bytes = base64.b64decode(image_data)
            
            # Convert to numpy array for face_recognition
            nparr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Process the image for face recognition
            conn = get_db_conn()
            c = conn.cursor()
            
            # Load known faces
            known_encodings = []
            known_ids = []
            
            c.execute("SELECT id, name, roll, face_encoding FROM students")
            students = c.fetchall()
            
            for student in students:
                student_id, name, roll, encoding_blob = student
                if encoding_blob:
                    encoding = np.frombuffer(encoding_blob, dtype=np.float64)
                    known_encodings.append(encoding)
                    known_ids.append(student_id)
            
            # Find faces in the frame
            face_locations = face_recognition.face_locations(frame)
            face_encodings = face_recognition.face_encodings(frame, face_locations)
            
            if not face_encodings:
                return jsonify({"success": False, "message": "No face detected in the image"})
            
            # Check if the face matches any known faces
            for face_encoding in face_encodings:
                matches = face_recognition.compare_faces(known_encodings, face_encoding)
                
                if True in matches:
                    match_index = matches.index(True)
                    student_id = known_ids[match_index]
                    
                    # Get student details
                    c.execute("SELECT name, roll FROM students WHERE id = ?", (student_id,))
                    student = c.fetchone()
                    name, roll = student
                    
                    # Check if already marked attendance today
                    today = datetime.datetime.now().strftime("%Y-%m-%d")
                    c.execute("SELECT id FROM attendance WHERE student_id = ? AND date(timestamp) = ?", 
                              (student_id, today))
                    
                    if c.fetchone():
                        return jsonify({"success": True, "message": f"Attendance already marked for {name} (Roll: {roll})"})
                    
                    # Mark attendance
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    c.execute("INSERT INTO attendance (student_id, timestamp) VALUES (?, ?)", 
                              (student_id, timestamp))
                    conn.commit()
                    
                    return jsonify({"success": True, "message": f"Attendance marked for {name} (Roll: {roll})"})
            
            return jsonify({"success": False, "message": "Face not recognized"})
            
        except Exception as e:
            return jsonify({"success": False, "message": f"Error: {str(e)}"})
        finally:
            if 'conn' in locals():
                conn.close()
    
    # For GET requests (render the page)
    return render_template("index.html")


@attendance_bp.route("/logs")
def view_logs():
    if "admin" not in session:
        return redirect(url_for("admin.login"))

    # Get date from request, default to today
    import datetime
    req_date = request.args.get('date', datetime.date.today().strftime('%Y-%m-%d'))

    conn = get_db_conn()
    c = conn.cursor()
    
    # If date is provided, filter by date
    if req_date:
        c.execute("""
            SELECT a.id, s.name, s.roll, a.timestamp 
            FROM attendance a 
            JOIN students s ON a.student_id = s.id 
            WHERE date(a.timestamp) = ? 
            ORDER BY a.timestamp DESC
        """, (req_date,))
    else:
        c.execute("""
            SELECT a.id, s.name, s.roll, a.timestamp 
            FROM attendance a 
            JOIN students s ON a.student_id = s.id 
            ORDER BY a.timestamp DESC
        """)
    
    records = c.fetchall()
    conn.close()

    return render_template("attendance.html", records=records, req_date=req_date)

@attendance_bp.route("/register", methods=["GET", "POST"])
def register_student():
    if "admin" not in session:
        return redirect(url_for("admin.login"))

    if request.method == "POST":
        try:
            name = request.form["name"].strip()
            roll = request.form["roll"].strip()
            
            # Check if image was uploaded via file input
            if 'image' in request.files and request.files['image'].filename != '':
                image_file = request.files['image']
                
                # Validate file type
                if image_file and allowed_file(image_file.filename):
                    # Process the uploaded image
                    image = Image.open(image_file)
                    
                    # Convert to numpy array for face_recognition
                    image_np = np.array(image)
                    
                    # Check if RGB (convert if not)
                    if len(image_np.shape) == 2:
                        # Convert grayscale to RGB
                        image_np = cv2.cvtColor(image_np, cv2.COLOR_GRAY2RGB)
                    elif image_np.shape[2] == 4:
                        # Convert RGBA to RGB
                        image_np = cv2.cvtColor(image_np, cv2.COLOR_RGBA2RGB)
                    
                    # Detect faces
                    face_locations = face_recognition.face_locations(image_np)
                    if not face_locations:
                        flash("No face detected in the uploaded image. Please try again with a clearer photo.", "error")
                        return render_template("register.html")
                        
                    # Generate face encoding
                    face_encoding = face_recognition.face_encodings(image_np, face_locations)[0]
                    
                    # Save the image file
                    os.makedirs(KNOWN_FACES_DIR, exist_ok=True)
                    save_path = os.path.join(KNOWN_FACES_DIR, f"{name}_{roll}.jpg")
                    
                    # Convert and save as JPEG
                    if image.mode != 'RGB':
                        image = image.convert('RGB')
                    image.save(save_path, 'JPEG')
                    
                    # Save student to database
                    conn = get_db_conn()
                    c = conn.cursor()
                    
                    # Get the next sequential ID
                    c.execute("SELECT COUNT(*) FROM students")
                    next_id = c.fetchone()[0] + 1
                    
                    # Get class and section
                    class_name = request.form.get('class', '').strip()
                    section = request.form.get('section', '').strip()
                    
                    # Insert with specific ID
                    c.execute("INSERT INTO students (id, name, roll, class, section, face_encoding) VALUES (?, ?, ?, ?, ?, ?)", 
                            (next_id, name, roll, class_name, section, face_encoding.tobytes()))
                    conn.commit()
                    conn.close()
                    
                    flash(f'Student {name} (Roll: {roll}, Class: {class_name}, Section: {section}) registered successfully with ID: {next_id}', 'success')
                    return redirect(url_for('attendance.students'))
                else:
                    flash('Please upload a valid image file (PNG, JPG, JPEG)', 'error')
            # Check if image was captured via webcam (sent as base64)
            elif 'capturedImage' in request.form and request.form['capturedImage']:
                try:
                    # Get the base64 image data
                    image_data = request.form['capturedImage']
                    # Remove the data URL prefix if present
                    if 'data:image' in image_data:
                        image_data = image_data.split(',')[1]
                    
                    # Decode base64 to binary
                    image_binary = base64.b64decode(image_data)
                    
                    # Open as PIL Image
                    image = Image.open(BytesIO(image_binary))
                    
                    # Convert to numpy array for face_recognition
                    image_np = np.array(image)
                    
                    # Check if RGB (convert if not)
                    if len(image_np.shape) == 2:
                        # Convert grayscale to RGB
                        image_np = cv2.cvtColor(image_np, cv2.COLOR_GRAY2RGB)
                    elif image_np.shape[2] == 4:
                        # Convert RGBA to RGB
                        image_np = cv2.cvtColor(image_np, cv2.COLOR_RGBA2RGB)
                    
                    # Detect faces
                    face_locations = face_recognition.face_locations(image_np)
                    if not face_locations:
                        flash("No face detected in the captured image. Please try again with a clearer photo.", "error")
                        return render_template("register.html")
                        
                    # Generate face encoding
                    face_encoding = face_recognition.face_encodings(image_np, face_locations)[0]
                    
                    # Save the image file
                    os.makedirs(KNOWN_FACES_DIR, exist_ok=True)
                    save_path = os.path.join(KNOWN_FACES_DIR, f"{name}_{roll}.jpg")
                    
                    # Convert and save as JPEG
                    if image.mode != 'RGB':
                        image = image.convert('RGB')
                    image.save(save_path, 'JPEG')
                    
                    # Save student to database
                    conn = get_db_conn()
                    c = conn.cursor()
                    
                    # Get the next sequential ID
                    c.execute("SELECT COUNT(*) FROM students")
                    next_id = c.fetchone()[0] + 1
                    
                    # Get class and section
                    class_name = request.form.get('class', '').strip()
                    section = request.form.get('section', '').strip()
                    
                    # Insert with specific ID
                    c.execute("INSERT INTO students (id, name, roll, class, section, face_encoding) VALUES (?, ?, ?, ?, ?, ?)", 
                            (next_id, name, roll, class_name, section, face_encoding.tobytes()))
                    conn.commit()
                    conn.close()
                    
                    flash(f'Student {name} (Roll: {roll}, Class: {class_name}, Section: {section}) registered successfully with ID: {next_id}', 'success')
                    return redirect(url_for('attendance.students'))
                except Exception as e:
                    flash(f'Error processing captured image: {str(e)}', 'error')
                    return render_template("register.html")
            else:
                flash('Please upload or capture a student photo', 'error')
        except Exception as e:
            flash(f'Error processing registration: {str(e)}', 'error')
            
    return render_template("register.html")

@attendance_bp.route("/students")
def students():
    if "admin" not in session:
        return redirect(url_for("admin.login"))
        
    conn = get_db_conn()
    c = conn.cursor()
    
    # Get filter parameters
    class_filter = request.args.get('class', '')
    section_filter = request.args.get('section', '')
    
    # Get all classes and sections for filter dropdowns
    c.execute("SELECT DISTINCT class FROM students WHERE class IS NOT NULL AND class != '' ORDER BY class")
    classes = [row[0] for row in c.fetchall()]
    
    c.execute("SELECT DISTINCT section FROM students WHERE section IS NOT NULL AND section != '' ORDER BY section")
    sections = [row[0] for row in c.fetchall()]
    
    # Apply filters if provided
    query = "SELECT id, name, roll, class, section FROM students"
    params = []
    
    if class_filter and section_filter:
        query += " WHERE class = ? AND section = ?"
        params.extend([class_filter, section_filter])
    elif class_filter:
        query += " WHERE class = ?"
        params.append(class_filter)
    elif section_filter:
        query += " WHERE section = ?"
        params.append(section_filter)
    
    query += " ORDER BY name"
    
    c.execute(query, params)
    students = c.fetchall()
    conn.close()
    
    return render_template("students.html", students=students, classes=classes, sections=sections, 
                           class_filter=class_filter, section_filter=section_filter)

@attendance_bp.route("/student/<int:student_id>")
def view_student(student_id):
    if "admin" not in session:
        return redirect(url_for("admin.login"))
        
    conn = get_db_conn()
    c = conn.cursor()
    
    # Get student details
    c.execute("SELECT id, name, roll, class, section FROM students WHERE id = ?", (student_id,))
    student = c.fetchone()
    
    if not student:
        conn.close()
        return "Student not found", 404
    
    # Get student's attendance records
    c.execute("""SELECT a.timestamp 
               FROM attendance a 
               WHERE a.student_id = ? 
               ORDER BY a.timestamp DESC""", (student_id,))
    attendance_records = c.fetchall()
    
    conn.close()
    
    # Get the image path if it exists
    student_name = student[1]
    student_roll = student[2]
    image_filename = f"{student_name}_{student_roll}.jpg"
    image_path = os.path.join(KNOWN_FACES_DIR, image_filename)
    
    # Debug print
    print(f"Looking for image at: {image_path}")
    print(f"File exists: {os.path.exists(image_path)}")
    
    if not os.path.exists(image_path):
        image_path = None
    
    return render_template("student_detail.html", student=student, 
                           attendance_records=attendance_records,
                           image_path=image_path)

@attendance_bp.route("/student/<int:student_id>/image")
def serve_student_image(student_id):
    if "admin" not in session:
        return redirect(url_for("admin.login"))
        
    conn = get_db_conn()
    c = conn.cursor()
    
    # Get student details
    c.execute("SELECT name, roll FROM students WHERE id = ?", (student_id,))
    student = c.fetchone()
    conn.close()
    
    if not student:
        print(f"Student with ID {student_id} not found")
        return "Student not found", 404
    
    # Get the image path
    student_name = student[0]
    student_roll = student[1]
    image_filename = f"{student_name}_{student_roll}.jpg"
    image_path = os.path.join(KNOWN_FACES_DIR, image_filename)
    
    print(f"Serving image from: {image_path}")
    print(f"File exists: {os.path.exists(image_path)}")
    
    if not os.path.exists(image_path):
        return "Image not found", 404
    
    from flask import send_file
    return send_file(image_path, mimetype='image/jpeg')

@attendance_bp.route("/student_photo/<int:student_id>")
def student_photo(student_id):
    if "admin" not in session:
        return redirect(url_for("admin.login"))
        
    conn = get_db_conn()
    c = conn.cursor()
    
    # Get student details
    c.execute("SELECT name, roll FROM students WHERE id = ?", (student_id,))
    student = c.fetchone()
    conn.close()
    
    if not student:
        return "Student not found", 404
    
    # Get the image path
    student_name = student[0]
    student_roll = student[1]
    image_filename = f"{student_name}_{student_roll}.jpg"
    image_path = os.path.join(KNOWN_FACES_DIR, image_filename)
    
    if not os.path.exists(image_path):
        return "Image not found", 404
    
    from flask import send_file
    return send_file(image_path, mimetype='image/jpeg')

@attendance_bp.route("/student/<int:student_id>/edit", methods=["GET", "POST"])
def edit_student(student_id):
    if "admin" not in session:
        return redirect(url_for("admin.login"))
    
    conn = get_db_conn()
    c = conn.cursor()
    
    # Get student details
    c.execute("SELECT id, name, roll, class, section FROM students WHERE id = ?", (student_id,))
    student = c.fetchone()
    
    if not student:
        conn.close()
        return "Student not found", 404
    
    if request.method == "POST":
        try:
            # Get updated information
            name = request.form["name"].strip()
            roll = request.form["roll"].strip()
            class_name = request.form["class"].strip()
            section = request.form["section"].strip()
            
            # Get current student info for image renaming
            old_name = student[1]
            old_roll = student[2]
            
            # Update student record
            c.execute("UPDATE students SET name = ?, roll = ?, class = ?, section = ? WHERE id = ?", 
                     (name, roll, class_name, section, student_id))
            conn.commit()
            
            # Rename image file if it exists
            old_image_filename = f"{old_name}_{old_roll}.jpg"
            new_image_filename = f"{name}_{roll}.jpg"
            old_image_path = os.path.join(KNOWN_FACES_DIR, old_image_filename)
            new_image_path = os.path.join(KNOWN_FACES_DIR, new_image_filename)
            
            if os.path.exists(old_image_path) and old_image_filename != new_image_filename:
                os.rename(old_image_path, new_image_path)
            
            flash(f"Student information updated successfully", "success")
            return redirect(url_for("attendance.view_student", student_id=student_id))
            
        except Exception as e:
            flash(f"Error updating student information: {str(e)}", "error")
    
    conn.close()
    return render_template("edit_student.html", student=student)

@attendance_bp.route("/student/<int:student_id>/delete", methods=["POST"])
def delete_student(student_id):
    if "admin" not in session:
        return redirect(url_for("admin.login"))
    
    conn = get_db_conn()
    c = conn.cursor()
    
    # Get student details before deletion for image removal
    c.execute("SELECT name, roll FROM students WHERE id = ?", (student_id,))
    student = c.fetchone()
    
    if not student:
        conn.close()
        return "Student not found", 404
    
    # Delete attendance records first (foreign key constraint)
    c.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
    
    # Delete student record
    c.execute("DELETE FROM students WHERE id = ?", (student_id,))
    conn.commit()
    conn.close()
    
    # Remove student image if exists
    student_name = student[0]
    student_roll = student[1]
    image_filename = f"{student_name}_{student_roll}.jpg"
    image_path = os.path.join(KNOWN_FACES_DIR, image_filename)
    
    if os.path.exists(image_path):
        os.remove(image_path)
    
    # Redirect to students list with success message
    from flask import flash
    flash(f"Student {student_name} (Roll: {student_roll}) has been deleted successfully", "success")
    return redirect(url_for("attendance.students"))
