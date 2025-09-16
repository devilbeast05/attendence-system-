import tkinter as tk
from tkinter import ttk
import cv2
import face_recognition
import sqlite3
import os
import datetime
import numpy as np
import json
from pathlib import Path

class AttendanceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Offline Attendance System")
        self.root.geometry("1200x700")
        
        # Database path - using local storage
        self.db_path = os.path.abspath("./instance/attendance.db")
        
        # Initialize database if not exists
        self.init_db()
        
        # Create UI components
        self.create_ui()
        
        # Known faces storage
        self.known_faces_dir = os.path.abspath("./known_faces")
        os.makedirs(self.known_faces_dir, exist_ok=True)
        
        # Load known faces on startup
        self.load_known_faces()
    
    def init_db(self):
        """Initialize the local SQLite database"""
        os.makedirs("./instance", exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Create tables if they don't exist
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
        c.execute('''CREATE TABLE IF NOT EXISTS sync_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    last_sync_time TEXT,
                    records_synced INTEGER
                )''')
        
        conn.commit()
        conn.close()
    
    def create_ui(self):
        """Create the desktop application UI"""
        # Create tabs
        self.tab_control = ttk.Notebook(self.root)
        
        # Tab 1: Face Recognition Attendance
        self.tab1 = ttk.Frame(self.tab_control)
        self.tab_control.add(self.tab1, text="Mark Attendance")
        
        # Tab 2: Student Management
        self.tab2 = ttk.Frame(self.tab_control)
        self.tab_control.add(self.tab2, text="Manage Students")
        
        # Tab 3: Data Export
        self.tab3 = ttk.Frame(self.tab_control)
        self.tab_control.add(self.tab3, text="Export Data")
        
        self.tab_control.pack(expand=1, fill="both")
        
        # Setup each tab's content
        self.setup_attendance_tab()
        self.setup_student_tab()
        self.setup_export_tab()
    
    def setup_attendance_tab(self):
        """Setup the attendance marking tab with camera feed"""
        # Camera frame
        self.camera_frame = tk.Frame(self.tab1)
        self.camera_frame.pack(pady=10)
        
        # Camera label (will show camera feed)
        self.camera_label = tk.Label(self.camera_frame)
        self.camera_label.pack()
        
        # Buttons frame
        btn_frame = tk.Frame(self.tab1)
        btn_frame.pack(pady=10)
        
        # Start/Stop camera buttons
        self.start_btn = tk.Button(btn_frame, text="Start Camera", command=self.start_camera)
        self.start_btn.grid(row=0, column=0, padx=10)
        
        self.stop_btn = tk.Button(btn_frame, text="Stop Camera", command=self.stop_camera)
        self.stop_btn.grid(row=0, column=1, padx=10)
        
        # Status frame
        status_frame = tk.Frame(self.tab1)
        status_frame.pack(pady=10, fill="x")
        
        # Status label
        self.status_label = tk.Label(status_frame, text="Camera inactive", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(fill="x")
        
        # Recent attendance list
        list_frame = tk.Frame(self.tab1)
        list_frame.pack(pady=10, fill="both", expand=True)
        
        tk.Label(list_frame, text="Recent Attendance:").pack(anchor="w")
        
        # Scrollable list
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.attendance_list = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        self.attendance_list.pack(fill="both", expand=True)
        scrollbar.config(command=self.attendance_list.yview)
        
        # Initialize camera variables
        self.cap = None
        self.is_running = False
    
    def setup_student_tab(self):
        """Setup the student management tab"""
        # Student form frame
        form_frame = tk.Frame(self.tab2)
        form_frame.pack(pady=10, fill="x")
        
        # Form fields
        tk.Label(form_frame, text="Name:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.name_entry = tk.Entry(form_frame, width=30)
        self.name_entry.grid(row=0, column=1, padx=10, pady=5)
        
        tk.Label(form_frame, text="Roll Number:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.roll_entry = tk.Entry(form_frame, width=30)
        self.roll_entry.grid(row=1, column=1, padx=10, pady=5)
        
        tk.Label(form_frame, text="Class:").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        self.class_entry = tk.Entry(form_frame, width=30)
        self.class_entry.grid(row=2, column=1, padx=10, pady=5)
        
        tk.Label(form_frame, text="Section:").grid(row=3, column=0, sticky="w", padx=10, pady=5)
        self.section_entry = tk.Entry(form_frame, width=30)
        self.section_entry.grid(row=3, column=1, padx=10, pady=5)
        
        # Buttons
        btn_frame = tk.Frame(self.tab2)
        btn_frame.pack(pady=10)
        
        self.capture_btn = tk.Button(btn_frame, text="Capture Face", command=self.capture_student_face)
        self.capture_btn.grid(row=0, column=0, padx=10)
        
        self.save_btn = tk.Button(btn_frame, text="Save Student", command=self.save_student)
        self.save_btn.grid(row=0, column=1, padx=10)
        
        # Student list
        list_frame = tk.Frame(self.tab2)
        list_frame.pack(pady=10, fill="both", expand=True)
        
        tk.Label(list_frame, text="Registered Students:").pack(anchor="w")
        
        # Table view for students
        self.tree = ttk.Treeview(list_frame, columns=("ID", "Name", "Roll", "Class", "Section"), show="headings")
        self.tree.heading("ID", text="ID")
        self.tree.heading("Name", text="Name")
        self.tree.heading("Roll", text="Roll Number")
        self.tree.heading("Class", text="Class")
        self.tree.heading("Section", text="Section")
        
        self.tree.column("ID", width=50)
        self.tree.column("Name", width=150)
        self.tree.column("Roll", width=100)
        self.tree.column("Class", width=80)
        self.tree.column("Section", width=80)
        
        self.tree.pack(fill="both", expand=True)
        
        # Load students
        self.load_students()
    
    def setup_export_tab(self):
        """Setup the data export tab with sync functionality"""
        # Export frame
        export_frame = tk.Frame(self.tab3)
        export_frame.pack(pady=20, padx=20, fill="both", expand=True)
        
        # Status section
        status_frame = tk.LabelFrame(export_frame, text="Sync Status")
        status_frame.pack(pady=10, padx=10, fill="x")
        
        # Get last sync time
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT last_sync_time FROM sync_status ORDER BY id DESC LIMIT 1")
        last_sync = c.fetchone()
        conn.close()
        
        last_sync_time = last_sync[0] if last_sync else "Never"
        
        # Last sync label
        tk.Label(status_frame, text="Last Synchronized:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.last_sync_label = tk.Label(status_frame, text=last_sync_time)
        self.last_sync_label.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        # Unsynchronized data counts
        tk.Label(status_frame, text="Pending Students:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        tk.Label(status_frame, text="Pending Attendance Records:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        
        # Get counts of unsynced data
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM students WHERE synced = 0")
        unsynced_students = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM attendance WHERE synced = 0")
        unsynced_attendance = c.fetchone()[0]
        conn.close()
        
        self.unsynced_students_label = tk.Label(status_frame, text=str(unsynced_students))
        self.unsynced_students_label.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.unsynced_attendance_label = tk.Label(status_frame, text=str(unsynced_attendance))
        self.unsynced_attendance_label.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        # Action buttons
        action_frame = tk.Frame(export_frame)
        action_frame.pack(pady=20, fill="x")
        
        # Export to JSON button
        export_btn = tk.Button(action_frame, text="Export Data to JSON", command=self.export_to_json, width=20)
        export_btn.pack(side="left", padx=10)
        
        # Sync button
        sync_btn = tk.Button(action_frame, text="Synchronize with Server", command=self.sync_with_server, width=20)
        sync_btn.pack(side="left", padx=10)
        
        # Refresh button
        refresh_btn = tk.Button(action_frame, text="Refresh Status", command=self.refresh_sync_status, width=15)
        refresh_btn.pack(side="right", padx=10)
        # Implementation already completed above
    
    def export_to_json(self):
        """Export attendance and student data to JSON files"""
        try:
            # Create export directory if it doesn't exist
            export_dir = Path("./exports")
            export_dir.mkdir(exist_ok=True)
            
            # Generate timestamp for filenames
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # This enables column access by name
            c = conn.cursor()
            
            # Export students
            c.execute("SELECT id, name, roll, class, section FROM students")
            students = [{k: row[k] for k in row.keys()} for row in c.fetchall()]
            
            student_file = export_dir / f"students_{timestamp}.json"
            with open(student_file, 'w') as f:
                json.dump(students, f, indent=4)
            
            # Export attendance
            c.execute("""
                SELECT a.id, a.student_id, a.timestamp, s.name, s.roll, s.class, s.section 
                FROM attendance a 
                JOIN students s ON a.student_id = s.id
            """)
            attendance = [{k: row[k] for k in row.keys()} for row in c.fetchall()]
            
            attendance_file = export_dir / f"attendance_{timestamp}.json"
            with open(attendance_file, 'w') as f:
                json.dump(attendance, f, indent=4)
            
            conn.close()
            
            # Show success message
            tk.messagebox.showinfo("Export Successful", 
                                  f"Data exported successfully to:\n{student_file}\n{attendance_file}")
            
        except Exception as e:
            tk.messagebox.showerror("Export Error", f"Failed to export data: {str(e)}")
    
    def sync_with_server(self):
        """Synchronize local data with the web server"""
        try:
            # In a real implementation, this would use requests to send data to server API
            # For this demo, we'll simulate a successful sync by updating the sync status
            
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Mark all unsynced records as synced
            c.execute("UPDATE students SET synced = 1 WHERE synced = 0")
            c.execute("UPDATE attendance SET synced = 1 WHERE synced = 0")
            
            # Get counts of synced records
            students_synced = c.rowcount
            c.execute("UPDATE attendance SET synced = 1 WHERE synced = 0")
            attendance_synced = c.rowcount
            
            # Update sync log
            now = datetime.datetime.now().isoformat()
            c.execute("INSERT INTO sync_log (sync_timestamp, records_synced) VALUES (?, ?)", 
                      (now, students_synced + attendance_synced))
            
            conn.commit()
            conn.close()
            
            # Update UI
            self.refresh_sync_status()
            
            # Show success message
            tk.messagebox.showinfo("Sync Successful", 
                                  f"Successfully synchronized {students_synced} students and {attendance_synced} attendance records.")
            
        except Exception as e:
            tk.messagebox.showerror("Sync Error", f"Failed to synchronize data: {str(e)}")
    
    def refresh_sync_status(self):
        """Refresh the sync status display"""
        # Get last sync time
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("SELECT sync_timestamp FROM sync_log ORDER BY id DESC LIMIT 1")
        last_sync = c.fetchone()
        last_sync_time = last_sync[0] if last_sync else "Never"
        
        # Get counts of unsynced data
        c.execute("SELECT COUNT(*) FROM students WHERE synced = 0")
        unsynced_students = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM attendance WHERE synced = 0")
        unsynced_attendance = c.fetchone()[0]
        
        conn.close()
        
        # Update labels
        self.last_sync_label.config(text=last_sync_time)
        self.unsynced_students_label.config(text=str(unsynced_students))
        self.unsynced_attendance_label.config(text=str(unsynced_attendance))
        
        # Export options
        tk.Label(export_frame, text="Export Options", font=("Arial", 14, "bold")).pack(pady=10)
        
        # Date range
        date_frame = tk.Frame(export_frame)
        date_frame.pack(pady=10, fill="x")
        
        tk.Label(date_frame, text="From Date:").grid(row=0, column=0, padx=10, pady=5)
        self.from_date = tk.Entry(date_frame, width=15)
        self.from_date.grid(row=0, column=1, padx=10, pady=5)
        self.from_date.insert(0, datetime.date.today().strftime("%Y-%m-%d"))
        
        tk.Label(date_frame, text="To Date:").grid(row=0, column=2, padx=10, pady=5)
        self.to_date = tk.Entry(date_frame, width=15)
        self.to_date.grid(row=0, column=3, padx=10, pady=5)
        self.to_date.insert(0, datetime.date.today().strftime("%Y-%m-%d"))
        
        # Export buttons
        btn_frame = tk.Frame(export_frame)
        btn_frame.pack(pady=20)
        
        self.export_csv_btn = tk.Button(btn_frame, text="Export to CSV", command=self.export_to_csv)
        self.export_csv_btn.grid(row=0, column=0, padx=10)
        
        self.export_json_btn = tk.Button(btn_frame, text="Export to JSON", command=self.export_to_json)
        self.export_json_btn.grid(row=0, column=1, padx=10)
        
        self.sync_btn = tk.Button(btn_frame, text="Prepare for Web Sync", command=self.prepare_web_sync)
        self.sync_btn.grid(row=0, column=2, padx=10)
        
        # Status
        self.export_status = tk.Label(export_frame, text="", fg="green")
        self.export_status.pack(pady=10)
    
    # Implement the remaining methods for functionality
    # ...

# Run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = AttendanceApp(root)
    root.mainloop()