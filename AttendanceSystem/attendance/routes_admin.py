from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import check_password_hash, generate_password_hash
import os
import json
import datetime
from .db import DB_PATH

# --- Blueprint setup ---
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def get_db_conn():
    return sqlite3.connect(DB_PATH)


# ---------- Routes ----------

@admin_bp.route('/portal-selection')
def portal_selection():
    return render_template('portal_selection.html')

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db_conn()
        c = conn.cursor()
        c.execute("SELECT password_hash FROM admin WHERE username = ?", (username,))
        row = c.fetchone()
        conn.close()

        if row and check_password_hash(row[0], password):
            session['admin'] = username
            return redirect(url_for('admin.dashboard'))
        else:
            error = "Invalid username or password"

    # render the login template
    return render_template('login.html', error=error)


@admin_bp.route('/dashboard')
def dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin.login'))
    
    # Get statistics for dashboard
    conn = get_db_conn()
    c = conn.cursor()
    
    # Get student count
    c.execute("SELECT COUNT(*) FROM students")
    student_count = c.fetchone()[0]
    
    # Get today's attendance count
    import datetime
    today = datetime.date.today().strftime('%Y-%m-%d')
    c.execute("SELECT COUNT(*) FROM attendance WHERE date(timestamp) = ?", (today,))
    today_attendance = c.fetchone()[0]
    
    # Get total records
    c.execute("SELECT COUNT(*) FROM attendance")
    total_records = c.fetchone()[0]
    
    # Calculate attendance rate (if students exist)
    attendance_rate = '0%'
    if student_count > 0:
        attendance_rate = f"{int((today_attendance / student_count) * 100)}%"
    
    conn.close()
    
    return render_template('dashboard.html', 
                           student_count=student_count,
                           today_attendance=today_attendance,
                           total_records=total_records,
                           attendance_rate=attendance_rate)


@admin_bp.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('admin.login'))


@admin_bp.route('/settings', methods=['GET'])
def settings():
    if 'admin' not in session:
        return redirect(url_for('admin.login'))
    
    # Get any success or error messages from flash
    success = None
    message = None
    if 'success' in session:
        success = session.pop('success')
        message = session.pop('message', None)
    
    return render_template('settings.html', success=success, message=message)


@admin_bp.route('/update-username', methods=['POST'])
def update_username():
    if 'admin' not in session:
        return redirect(url_for('admin.login'))
    
    current_username = session.get('admin')
    new_username = request.form.get('new_username')
    password = request.form.get('password')
    
    # Validate inputs
    if not new_username or not password:
        session['success'] = False
        session['message'] = "All fields are required"
        return redirect(url_for('admin.settings'))
    
    # Check if the password is correct
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT password_hash FROM admin WHERE username = ?", (current_username,))
    row = c.fetchone()
    
    if not row or not check_password_hash(row[0], password):
        session['success'] = False
        session['message'] = "Incorrect password"
        conn.close()
        return redirect(url_for('admin.settings'))
    
    # Update the username
    c.execute("UPDATE admin SET username = ? WHERE username = ?", (new_username, current_username))
    conn.commit()
    conn.close()
    
    # Update the session
    session['admin'] = new_username
    session['success'] = True
    session['message'] = "Username updated successfully"
    
    return redirect(url_for('admin.settings'))


@admin_bp.route('/update-password', methods=['POST'])
def update_password():
    if 'admin' not in session:
        return redirect(url_for('admin.login'))
    
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Validate inputs
    if not current_password or not new_password or not confirm_password:
        session['success'] = False
        session['message'] = "All fields are required"
        return redirect(url_for('admin.settings'))
    
    if new_password != confirm_password:
        session['success'] = False
        session['message'] = "New passwords do not match"
        return redirect(url_for('admin.settings'))
    
    # Check if the current password is correct
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT password_hash FROM admin WHERE username = ?", (session.get('admin'),))
    row = c.fetchone()
    
    if not row or not check_password_hash(row[0], current_password):
        session['success'] = False
        session['message'] = "Current password is incorrect"
        conn.close()
        return redirect(url_for('admin.settings'))
    
    # Update the password
    new_password_hash = generate_password_hash(new_password)
    c.execute("UPDATE admin SET password_hash = ? WHERE username = ?", (new_password_hash, session.get('admin')))
    conn.commit()
    conn.close()
    
    session['success'] = True
    session['message'] = "Password updated successfully"
    
    return redirect(url_for('admin.settings'))


@admin_bp.route('/register', methods=['GET', 'POST'])
def admin_register():
    if 'admin' not in session:
        return redirect(url_for('admin.login'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        roll = request.form.get('roll', '').strip()
        
        if not name or not roll:
            flash('Name and roll number are required', 'error')
            return render_template('register.html')
        
        # Handle file upload
        if 'image' not in request.files:
            flash('Please select an image file', 'error')
            return render_template('register.html')
        
        file = request.files['image']
        if file.filename == '':
            flash('Please select an image file', 'error')
            return render_template('register.html')
        
        if file and file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            import face_recognition
            import numpy as np
            from PIL import Image
            import io
            
            try:
                # Read and process the uploaded image
                image_data = file.read()
                image = Image.open(io.BytesIO(image_data))
                image_array = np.array(image)
                
                # Generate face encoding
                face_locations = face_recognition.face_locations(image_array)
                if not face_locations:
                    flash('No face detected in the image. Please upload a clear photo with a visible face.', 'error')
                    return render_template('register.html')
                
                face_encodings = face_recognition.face_encodings(image_array, face_locations)
                if not face_encodings:
                    flash('Could not generate face encoding. Please try with a different image.', 'error')
                    return render_template('register.html')
                
                face_encoding = face_encodings[0]
                
                # Save student to database with reassigned ID
                conn = get_db_conn()
                c = conn.cursor()
                
                # Get the next sequential ID based on current count
                c.execute("SELECT COUNT(*) FROM students")
                next_id = c.fetchone()[0] + 1
                
                # Insert with specific ID
                c.execute("INSERT INTO students (id, name, roll, face_encoding) VALUES (?, ?, ?, ?)", 
                         (next_id, name, roll, face_encoding.tobytes()))
                
                # Save the image file
                import os
                KNOWN_FACES_DIR = "attendance/known_faces"
                os.makedirs(KNOWN_FACES_DIR, exist_ok=True)
                save_path = os.path.join(KNOWN_FACES_DIR, f"{name}_{roll}.jpg")
                
                # Convert and save as JPEG
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                image.save(save_path, 'JPEG')
                
                conn.commit()
                conn.close()
                
                flash(f'Student {name} (Roll: {roll}) registered successfully with ID: {next_id}', 'success')
                return redirect(url_for('admin.dashboard'))
                
            except Exception as e:
                flash(f'Error processing image: {str(e)}', 'error')
                return render_template('register.html')
        else:
            flash('Please upload a valid image file (PNG, JPG, JPEG)', 'error')
            return render_template('register.html')
    
    return render_template('register.html')

@admin_bp.route('/dashboard')
def admin_dashboard():
    return dashboard()

@admin_bp.route('/analytics')
def analytics():
    if 'admin' not in session:
        return redirect(url_for('admin.login'))
    
    # Get date range from query params or use current month
    today = datetime.date.today()
    start_date = request.args.get('start_date', (today.replace(day=1)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', today.strftime('%Y-%m-%d'))
    
    conn = get_db_conn()
    c = conn.cursor()
    
    # Get daily attendance counts
    c.execute("""
        SELECT date(timestamp) as date, COUNT(*) as count 
        FROM attendance 
        WHERE date(timestamp) BETWEEN ? AND ? 
        GROUP BY date(timestamp) 
        ORDER BY date(timestamp)
    """, (start_date, end_date))
    daily_counts = c.fetchall()
    
    # Get attendance by class
    c.execute("""
        SELECT s.class, COUNT(a.id) as count 
        FROM attendance a 
        JOIN students s ON a.student_id = s.id 
        WHERE date(a.timestamp) BETWEEN ? AND ? 
        GROUP BY s.class 
        ORDER BY count DESC
    """, (start_date, end_date))
    class_attendance = c.fetchall()
    
    # Get attendance by section
    c.execute("""
        SELECT s.section, COUNT(a.id) as count 
        FROM attendance a 
        JOIN students s ON a.student_id = s.id 
        WHERE date(a.timestamp) BETWEEN ? AND ? 
        GROUP BY s.section 
        ORDER BY count DESC
    """, (start_date, end_date))
    section_attendance = c.fetchall()
    
    # Get attendance trend by hour
    c.execute("""
        SELECT strftime('%H', timestamp) as hour, COUNT(*) as count 
        FROM attendance 
        WHERE date(timestamp) BETWEEN ? AND ? 
        GROUP BY hour 
        ORDER BY hour
    """, (start_date, end_date))
    hourly_trend = c.fetchall()
    
    # Convert data for charts
    dates = [row[0] for row in daily_counts]
    counts = [row[1] for row in daily_counts]
    
    class_labels = [row[0] for row in class_attendance]
    class_data = [row[1] for row in class_attendance]
    
    section_labels = [row[0] for row in section_attendance]
    section_data = [row[1] for row in section_attendance]
    
    hours = [row[0] for row in hourly_trend]
    hourly_data = [row[1] for row in hourly_trend]
    
    conn.close()
    
    # Return the analytics template with the data
    return render_template('analytics_page.html',
                          start_date=start_date,
                          end_date=end_date,
                          daily_counts=daily_counts,
                          class_attendance=class_attendance,
                          section_attendance=section_attendance,
                          hourly_trend=hourly_trend,
                          dates=json.dumps(dates),
                          counts=json.dumps(counts),
                          class_labels=json.dumps(class_labels),
                          class_data=json.dumps(class_data),
                          section_labels=json.dumps(section_labels),
                          section_data=json.dumps(section_data),
                          hours=json.dumps(hours),
                          hourly_data=json.dumps(hourly_data))

@admin_bp.route('/reassign-ids', methods=['POST'])
def reassign_student_ids():
    if 'admin' not in session:
        return redirect(url_for('admin.login'))
    
    try:
        conn = get_db_conn()
        c = conn.cursor()
        
        # Get all students ordered by their current ID
        c.execute("SELECT id, name, roll, face_encoding FROM students ORDER BY id")
        students = c.fetchall()
        
        if not students:
            flash('No students found to reassign IDs', 'info')
            return redirect(url_for('admin.dashboard'))
        
        # Create a temporary table to store the reassigned data
        c.execute("""CREATE TEMPORARY TABLE students_temp (
                        id INTEGER PRIMARY KEY,
                        name TEXT,
                        roll TEXT,
                        face_encoding BLOB
                    )""")
        
        # Insert students with new sequential IDs
        for new_id, (old_id, name, roll, face_encoding) in enumerate(students, 1):
            c.execute("INSERT INTO students_temp (id, name, roll, face_encoding) VALUES (?, ?, ?, ?)",
                     (new_id, name, roll, face_encoding))
        
        # Update attendance records to use new IDs
        id_mapping = {old_id: new_id for new_id, (old_id, _, _, _) in enumerate(students, 1)}
        
        for old_id, new_id in id_mapping.items():
            c.execute("UPDATE attendance SET student_id = ? WHERE student_id = ?", (new_id, old_id))
        
        # Replace the original table
        c.execute("DELETE FROM students")
        c.execute("INSERT INTO students SELECT * FROM students_temp")
        c.execute("DROP TABLE students_temp")
        
        # Reset the auto-increment counter
        max_id = len(students)
        c.execute(f"UPDATE sqlite_sequence SET seq = {max_id} WHERE name = 'students'")
        
        conn.commit()
        conn.close()
        
        flash(f'Successfully reassigned IDs for {len(students)} students. IDs now run from 1 to {len(students)}.', 'success')
        
    except Exception as e:
        flash(f'Error reassigning student IDs: {str(e)}', 'error')
    
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/export-csv', endpoint='export_csv')
def export_csv():
    if 'admin' not in session:
        return redirect(url_for('admin.login'))
    
    # Get the date parameter
    date = request.args.get('date')
    
    # Connect to database
    conn = get_db_conn()
    c = conn.cursor()
    
    # Query for attendance records for the specified date
    if date:
        c.execute("""
            SELECT s.roll, s.name, a.timestamp 
            FROM attendance a 
            JOIN students s ON a.student_id = s.id 
            WHERE date(a.timestamp) = ? 
            ORDER BY a.timestamp
        """, (date,))
    else:
        # If no date specified, get all records
        c.execute("""
            SELECT s.roll, s.name, a.timestamp 
            FROM attendance a 
            JOIN students s ON a.student_id = s.id 
            ORDER BY a.timestamp
        """)
    
    records = c.fetchall()
    conn.close()
    
    # Create CSV response
    from flask import Response
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Roll Number', 'Name', 'Timestamp'])
    
    # Write data
    for record in records:
        writer.writerow(record)
    
    # Create response
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers["Content-Disposition"] = f"attachment; filename=attendance_{date or 'all'}.csv"
    
    return response
