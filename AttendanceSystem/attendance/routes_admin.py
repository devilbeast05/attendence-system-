from flask import Blueprint, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import check_password_hash

# --- Blueprint setup ---
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

DB_PATH = "attendance.db"


def get_db_conn():
    return sqlite3.connect(DB_PATH)


# ---------- Routes ----------

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
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
            return "Invalid username or password", 401

    # render a simple login page
    return """
    <h2>Admin Login</h2>
    <form method="post">
      Username: <input name="username"><br>
      Password: <input type="password" name="password"><br>
      <button type="submit">Login</button>
    </form>
    """


@admin_bp.route('/dashboard')
def dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin.login'))

    return """
    <h2>Admin Dashboard</h2>
    <p>Welcome, {}</p>
    <ul>
      <li><a href="/admin/register">Register new student</a></li>
      <li><a href="/admin/students">List students</a></li>
      <li><a href="/admin/attendance">View attendance</a></li>
      <li><a href="/admin/logout">Logout</a></li>
    </ul>
    """.format(session['admin'])


@admin_bp.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('admin.login'))
