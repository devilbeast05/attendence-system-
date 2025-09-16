from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3
import datetime
import os
import json
from .db import DB_PATH

# --- Blueprint setup ---
gov_bp = Blueprint('gov', __name__, url_prefix='/gov')

def get_db_conn():
    return sqlite3.connect(DB_PATH)

# --- Authentication ---
@gov_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Validate government credentials (would use a separate table in production)
        if username == "gov_user" and password == "gov_password":
            session['gov'] = username
            return redirect(url_for('gov.dashboard'))
        else:
            error = "Invalid government credentials"

    return render_template('gov_login.html', error=error)

@gov_bp.route('/logout')
def logout():
    session.pop('gov', None)
    return redirect(url_for('gov.login'))

# --- Dashboard ---
@gov_bp.route('/dashboard')
def dashboard():
    if 'gov' not in session:
        return redirect(url_for('gov.login'))
    
    # Get statistics for dashboard
    conn = get_db_conn()
    c = conn.cursor()
    
    # Get student count
    c.execute("SELECT COUNT(*) FROM students")
    student_count = c.fetchone()[0]
    
    # Get today's attendance count
    today = datetime.date.today().strftime('%Y-%m-%d')
    c.execute("SELECT COUNT(*) FROM attendance WHERE date(timestamp) = ?", (today,))
    today_attendance = c.fetchone()[0]
    
    # Get total records
    c.execute("SELECT COUNT(*) FROM attendance")
    total_records = c.fetchone()[0]
    
    # Get attendance by class
    c.execute("""
        SELECT s.class, COUNT(a.id) as count 
        FROM attendance a 
        JOIN students s ON a.student_id = s.id 
        WHERE date(a.timestamp) = ? 
        GROUP BY s.class
    """, (today,))
    class_attendance = c.fetchall()
    
    # Get sync statistics
    c.execute("SELECT COUNT(*) FROM students WHERE synced = 1")
    students_synced = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM attendance WHERE synced = 1")
    attendance_synced = c.fetchone()[0]
    
    # Get last sync time
    c.execute("SELECT MAX(sync_timestamp) FROM sync_log")
    last_sync_result = c.fetchone()[0]
    last_sync = last_sync_result if last_sync_result else 'Never'
    
    conn.close()
    
    return render_template('gov_dashboard.html', 
                           student_count=student_count,
                           today_attendance=today_attendance,
                           total_records=total_records,
                           class_attendance=class_attendance,
                           students_synced=students_synced,
                           attendance_synced=attendance_synced,
                           last_sync=last_sync)

# --- Sync Status ---
@gov_bp.route('/sync_status')
def sync_status():
    if 'gov' not in session:
        return redirect(url_for('gov.login'))
    
    conn = get_db_conn()
    c = conn.cursor()
    
    # Get sync statistics
    c.execute("SELECT COUNT(*) FROM students WHERE synced = 1")
    students_synced = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM attendance WHERE synced = 1")
    attendance_synced = c.fetchone()[0]
    
    # Get last sync time
    c.execute("SELECT MAX(sync_timestamp) FROM sync_log")
    last_sync = c.fetchone()[0]
    
    # Get unsynced counts
    c.execute("SELECT COUNT(*) FROM students WHERE synced = 0")
    unsynced_students = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM attendance WHERE synced = 0")
    unsynced_attendance = c.fetchone()[0]
    
    conn.close()
    
    return render_template('gov_sync.html',
                           students_synced=students_synced,
                           attendance_synced=attendance_synced,
                           last_sync=last_sync if last_sync else 'Never',
                           unsynced_students=unsynced_students,
                           unsynced_attendance=unsynced_attendance)

# --- Attendance Reports ---
@gov_bp.route('/reports')
def reports():
    if 'gov' not in session:
        return redirect(url_for('gov.login'))
    
    # Get date from query params or use today
    req_date = request.args.get('date', datetime.date.today().strftime('%Y-%m-%d'))
    
    # Get class filter if provided
    class_filter = request.args.get('class', '')
    section_filter = request.args.get('section', '')
    
    conn = get_db_conn()
    c = conn.cursor()
    
    # Base query
    query = """
        SELECT s.id, s.name, s.roll, s.class, s.section, a.timestamp 
        FROM attendance a 
        JOIN students s ON a.student_id = s.id 
        WHERE date(a.timestamp) = ? 
    """
    params = [req_date]
    
    # Add filters if provided
    if class_filter:
        query += " AND s.class = ? "
        params.append(class_filter)
    if section_filter:
        query += " AND s.section = ? "
        params.append(section_filter)
    
    # Add order by
    query += " ORDER BY a.timestamp DESC"
    
    # Execute query
    c.execute(query, params)
    records = c.fetchall()
    
    # Get available classes and sections for filters
    c.execute("SELECT DISTINCT class FROM students ORDER BY class")
    classes = [row[0] for row in c.fetchall()]
    
    c.execute("SELECT DISTINCT section FROM students ORDER BY section")
    sections = [row[0] for row in c.fetchall()]
    
    conn.close()
    
    return render_template('gov_reports.html', records=records, req_date=req_date)

# --- API for data import ---
@gov_bp.route('/api/import', methods=['POST'])
def import_data():
    # This would be secured with proper API authentication in production
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    
    data = request.get_json()
    
    if 'attendance_records' not in data:
        return jsonify({"error": "No attendance records provided"}), 400
    
    conn = get_db_conn()
    c = conn.cursor()
    
    try:
        # Begin transaction
        conn.execute('BEGIN TRANSACTION')
        
        records_added = 0
        for record in data['attendance_records']:
            # Check if student exists by roll number
            c.execute("SELECT id FROM students WHERE roll = ?", (record['roll'],))
            student = c.fetchone()
            
            if not student:
                # Add student if not exists (without face encoding)
                c.execute("""
                    INSERT INTO students (name, roll, class, section) 
                    VALUES (?, ?, ?, ?)
                """, (record['name'], record['roll'], record['class'], record['section']))
                student_id = c.lastrowid
            else:
                student_id = student[0]
            
            # Add attendance record
            c.execute("""
                INSERT INTO attendance (student_id, timestamp) 
                VALUES (?, ?)
            """, (student_id, record['timestamp']))
            
            records_added += 1
        
        # Commit transaction
        conn.commit()
        
        return jsonify({
            "success": True,
            "message": f"Successfully imported {records_added} attendance records"
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# --- Analytics ---
@gov_bp.route('/analytics')
def analytics():
    if 'gov' not in session:
        return redirect(url_for('gov.login'))
    
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
    
    # We already have class_attendance and section_attendance, so we don't need these duplicate queries
    
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
    return render_template('gov_analytics.html',
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
    
# --- Export Data ---
@gov_bp.route('/export_data')
def export_data():
    if 'gov' not in session:
        return redirect(url_for('gov.login'))
    
    # Get date range from query params or use current month
    today = datetime.date.today()
    start_date = request.args.get('start_date', (today.replace(day=1)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', today.strftime('%Y-%m-%d'))
    
    conn = get_db_conn()
    c = conn.cursor()
    
    # Get all attendance records in the date range
    c.execute("""
        SELECT s.id, s.name, s.roll, s.class, s.section, a.timestamp 
        FROM attendance a 
        JOIN students s ON a.student_id = s.id 
        WHERE date(a.timestamp) BETWEEN ? AND ? 
        ORDER BY a.timestamp DESC
    """, (start_date, end_date))
    records = c.fetchall()
    
    conn.close()
    
    # Create CSV content
    import csv
    import io
    from flask import make_response
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['ID', 'Name', 'Roll Number', 'Class', 'Section', 'Timestamp'])
    
    # Write data
    for record in records:
        writer.writerow(record)
    
    # Create response
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=attendance_{start_date}_to_{end_date}.csv"
    response.headers["Content-type"] = "text/csv"
    
    return response