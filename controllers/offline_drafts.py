from flask import Blueprint, render_template

from controllers.auth import login_required


bp = Blueprint("offline_drafts", __name__, url_prefix="/offline-drafts")


@bp.get("/")
@login_required
def drafts_home():
    return render_template("offline_drafts.html")

