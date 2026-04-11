import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from models.db import get_connection
from controllers.auth import login_required

bp = Blueprint("settings", __name__, url_prefix="/settings")

def get_setting(key, default=None):
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM system_settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

def set_setting(key, value):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        conn.commit()

@bp.route("/branding", methods=["GET", "POST"])
@login_required
def branding():
    if request.method == "POST":
        # Handle new textual and boolean settings
        fields = [
            "system_name", "institution_name", "academic_year", 
            "current_semester", "timezone"
        ]
        
        for field in fields:
            val = request.form.get(field)
            if val is not None:
                set_setting(field, val)
                
        # Handle toggle switches (checkboxes)
        ml_detection = 'true' if request.form.get('ml_detection') else 'false'
        location_qr = 'true' if request.form.get('location_qr') else 'false'
        
        set_setting('ml_detection', ml_detection)
        set_setting('location_qr', location_qr)

        flash("System settings updated successfully!", "success")
        return redirect(url_for("settings.branding"))

    settings = {
        "system_name": get_setting("system_name", "SmartAttend Admin"),
        "institution_name": get_setting("institution_name", "Midlands State University"),
        "academic_year": get_setting("academic_year", "2025/2026"),
        "current_semester": get_setting("current_semester", "Semester 1"),
        "timezone": get_setting("timezone", "Africa/Harare (GMT+2)"),
        "ml_detection": get_setting("ml_detection", "true") == "true",
        "location_qr": get_setting("location_qr", "true") == "true",
    }
    return render_template("settings/branding.html", settings=settings)
