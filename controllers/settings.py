import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from models.db import get_connection
from controllers.auth import login_required

bp = Blueprint("settings", __name__, url_prefix="/settings")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

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
        # Handle text settings if any (e.g. System Name)
        system_name = request.form.get("system_name")
        if system_name:
            set_setting("system_name", system_name)

        # Handle file uploads
        for field in ["logo", "dashboard_banner", "login_bg"]:
            if field in request.files:
                file = request.files[field]
                if file and file.filename != "" and allowed_file(file.filename):
                    filename = secure_filename(f"{field}_{file.filename}")
                    
                    # Use environment variable for upload folder (for Render persistent disk)
                    upload_folder = os.environ.get("UPLOAD_FOLDER", os.path.join(current_app.root_path, "static", "uploads"))
                    
                    if not os.path.exists(upload_folder):
                        os.makedirs(upload_folder)
                    
                    file_path = os.path.join(upload_folder, filename)
                    file.save(file_path)
                    
                    # Store path. If it's the default static/uploads, store relative path.
                    # Otherwise, we might need a separate route to serve these files, 
                    # but for now we'll assume they are accessible or served via a static route.
                    if "UPLOAD_FOLDER" in os.environ:
                        # On Render, we'll need a way to serve these. 
                        # For simplicity, we'll store the filename and assume a dedicated route or symlink.
                        set_setting(field, f"uploads/{filename}")
                    else:
                        set_setting(field, f"uploads/{filename}")

        flash("Branding settings updated successfully!", "success")
        return redirect(url_for("settings.branding"))

    settings = {
        "system_name": get_setting("system_name", "TMS"),
        "logo": get_setting("logo"),
        "dashboard_banner": get_setting("dashboard_banner"),
        "login_bg": get_setting("login_bg"),
    }
    return render_template("settings/branding.html", settings=settings)
