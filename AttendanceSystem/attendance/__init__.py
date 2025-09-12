from flask import Flask
import os
from .db import init_db

def create_app():
    app = Flask(__name__)
    app.secret_key = os.urandom(24)
    app.config['UPLOAD_FOLDER'] = os.path.join("static", "uploads")
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # register blueprints
    from .routes_attendance import attendance_bp
    from .routes_admin import admin_bp
    app.register_blueprint(attendance_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    return app