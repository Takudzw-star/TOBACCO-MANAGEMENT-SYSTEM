from flask import Blueprint, render_template

from controllers.auth import login_required, roles_required
from models.db import get_connection


bp = Blueprint("map_view", __name__, url_prefix="/map")


@bp.get("/farmers")
@login_required
@roles_required("admin", "field_officer", "accounts")
def farmers_map():
    with get_connection() as conn:
        farmers = conn.execute(
            """
            SELECT id, name, lat, lng, address, land_size_ha
            FROM farmers
            WHERE lat IS NOT NULL AND lng IS NOT NULL
            ORDER BY id DESC
            """
        ).fetchall()

    points = [
        {
            "id": f["id"],
            "name": f["name"],
            "lat": float(f["lat"]),
            "lng": float(f["lng"]),
            "address": f["address"] or "",
            "land_size_ha": f["land_size_ha"],
        }
        for f in farmers
    ]

    return render_template("map/farmers.html", points=points)

