from flask import Blueprint, flash, redirect, render_template, request, url_for

from controllers.auth import login_required, roles_required
from models.db import get_connection


bp = Blueprint("farmers", __name__, url_prefix="/farmers")


@bp.get("/")
@login_required
@roles_required("admin", "field_officer")
def list_farmers():
    with get_connection() as conn:
        farmers = conn.execute(
            "SELECT id, name, contact_info, address, contract_status, land_size_ha, lat, lng FROM farmers ORDER BY id DESC"
        ).fetchall()
    return render_template("farmers/list.html", farmers=farmers)


@bp.get("/<int:farmer_id>")
@login_required
@roles_required("admin", "field_officer")
def farmer_detail(farmer_id: int):
    with get_connection() as conn:
        farmer = conn.execute(
            "SELECT id, name, contact_info, address, contract_status, land_size_ha, lat, lng FROM farmers WHERE id = ?",
            (farmer_id,),
        ).fetchone()

        if farmer is None:
            flash("Farmer not found.", "danger")
            return redirect(url_for("farmers.list_farmers"))

        contracts = conn.execute(
            """
            SELECT
              c.id AS contract_id,
              c.contract_date,
              c.details,
              fo.id AS field_officer_id,
              fo.name AS field_officer_name,
              fo.region AS field_officer_region,
              COALESCE(SUM(t.amount), 0) AS total_paid,
              MAX(t.transaction_date) AS last_payment_date
            FROM contracts c
            LEFT JOIN field_officers fo ON fo.id = c.field_officer_id
            LEFT JOIN transactions t ON t.contract_id = c.id
            WHERE c.farmer_id = ?
            GROUP BY c.id, c.contract_date, c.details, fo.id, fo.name, fo.region
            ORDER BY c.id DESC
            """,
            (farmer_id,),
        ).fetchall()

        totals = conn.execute(
            """
            SELECT
              COALESCE(SUM(t.amount), 0) AS total_paid,
              COUNT(DISTINCT c.id) AS contract_count,
              MAX(t.transaction_date) AS last_payment_date
            FROM farmers f
            LEFT JOIN contracts c ON c.farmer_id = f.id
            LEFT JOIN transactions t ON t.contract_id = c.id
            WHERE f.id = ?
            """,
            (farmer_id,),
        ).fetchone()

        yield_history = conn.execute(
            """
            SELECT y.season AS season, COALESCE(SUM(y.weight_kg), 0) AS total_kg
            FROM yields y
            JOIN contracts c ON c.id = y.contract_id
            WHERE c.farmer_id = ?
            GROUP BY y.season
            ORDER BY y.season DESC
            """,
            (farmer_id,),
        ).fetchall()

        crop_history = conn.execute(
            """
            SELECT id, season, crop, area_ha, notes
            FROM farmer_crops
            WHERE farmer_id = ?
            ORDER BY season DESC, id DESC
            LIMIT 10
            """,
            (farmer_id,),
        ).fetchall()

        # Productivity score (0-100) based on yield per hectare vs peers (same season, if possible).
        land_size_ha = farmer["land_size_ha"] or 0
        latest_season = yield_history[0]["season"] if yield_history else None
        productivity_score = None
        risk_level = "Unknown"

        if latest_season and land_size_ha and land_size_ha > 0:
            farmer_yield_kg = float(yield_history[0]["total_kg"] or 0)
            farmer_yph = farmer_yield_kg / float(land_size_ha)

            peer_rows = conn.execute(
                """
                SELECT f.id AS farmer_id,
                       COALESCE(SUM(y.weight_kg), 0) AS total_kg,
                       f.land_size_ha AS land_size_ha
                FROM farmers f
                JOIN contracts c ON c.farmer_id = f.id
                JOIN yields y ON y.contract_id = c.id
                WHERE y.season = ?
                  AND f.land_size_ha IS NOT NULL
                  AND f.land_size_ha > 0
                GROUP BY f.id, f.land_size_ha
                """,
                (latest_season,),
            ).fetchall()

            peer_yph = []
            for r in peer_rows:
                yph = float(r["total_kg"] or 0) / float(r["land_size_ha"])
                peer_yph.append(yph)
            peer_yph.sort()

            if peer_yph:
                # percentile rank (simple)
                less_equal = sum(1 for v in peer_yph if v <= farmer_yph)
                productivity_score = round(100 * less_equal / len(peer_yph))

        # Risk: based on last 2 seasons yield trend (decline) and "no yield" signals.
        if yield_history:
            if len(yield_history) >= 2:
                y0 = float(yield_history[0]["total_kg"] or 0)
                y1 = float(yield_history[1]["total_kg"] or 0)
                if y0 == 0 and y1 == 0:
                    risk_level = "High"
                elif y0 < y1 * 0.7:
                    risk_level = "High"
                elif y0 < y1 * 0.9:
                    risk_level = "Medium"
                else:
                    risk_level = "Low"
            else:
                risk_level = "Medium" if float(yield_history[0]["total_kg"] or 0) == 0 else "Low"

    return render_template(
        "farmers/detail.html",
        farmer=farmer,
        contracts=contracts,
        totals=totals,
        yield_history=yield_history,
        crop_history=crop_history,
        intelligence={
            "productivity_score": productivity_score,
            "risk_level": risk_level,
            "latest_season": latest_season,
        },
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "field_officer")
def create_farmer():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        contact_info = (request.form.get("contact_info") or "").strip() or None
        address = (request.form.get("address") or "").strip() or None
        contract_status = 1 if request.form.get("contract_status") == "on" else 0
        land_size_raw = (request.form.get("land_size_ha") or "").strip()
        lat_raw = (request.form.get("lat") or "").strip()
        lng_raw = (request.form.get("lng") or "").strip()

        land_size_ha = None
        lat = None
        lng = None
        if land_size_raw:
            try:
                land_size_ha = float(land_size_raw)
            except ValueError:
                flash("Land size must be a number (hectares).", "danger")
                return render_template("farmers/form.html", farmer=None)
        if lat_raw:
            try:
                lat = float(lat_raw)
            except ValueError:
                flash("Latitude must be a number.", "danger")
                return render_template("farmers/form.html", farmer=None)
        if lng_raw:
            try:
                lng = float(lng_raw)
            except ValueError:
                flash("Longitude must be a number.", "danger")
                return render_template("farmers/form.html", farmer=None)

        if not name:
            flash("Name is required.", "danger")
            return render_template("farmers/form.html", farmer=None)

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO farmers (name, contact_info, address, contract_status, land_size_ha, lat, lng)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (name, contact_info, address, contract_status, land_size_ha, lat, lng),
            )
            conn.commit()

        flash("Farmer created.", "success")
        return redirect(url_for("farmers.list_farmers"))

    return render_template("farmers/form.html", farmer=None)


@bp.route("/<int:farmer_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin", "field_officer")
def edit_farmer(farmer_id: int):
    with get_connection() as conn:
        farmer = conn.execute(
            "SELECT id, name, contact_info, address, contract_status, land_size_ha, lat, lng FROM farmers WHERE id = ?",
            (farmer_id,),
        ).fetchone()

    if farmer is None:
        flash("Farmer not found.", "danger")
        return redirect(url_for("farmers.list_farmers"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        contact_info = (request.form.get("contact_info") or "").strip() or None
        address = (request.form.get("address") or "").strip() or None
        contract_status = 1 if request.form.get("contract_status") == "on" else 0
        land_size_raw = (request.form.get("land_size_ha") or "").strip()
        lat_raw = (request.form.get("lat") or "").strip()
        lng_raw = (request.form.get("lng") or "").strip()

        land_size_ha = None
        lat = None
        lng = None
        if land_size_raw:
            try:
                land_size_ha = float(land_size_raw)
            except ValueError:
                flash("Land size must be a number (hectares).", "danger")
                return render_template("farmers/form.html", farmer=farmer)
        if lat_raw:
            try:
                lat = float(lat_raw)
            except ValueError:
                flash("Latitude must be a number.", "danger")
                return render_template("farmers/form.html", farmer=farmer)
        if lng_raw:
            try:
                lng = float(lng_raw)
            except ValueError:
                flash("Longitude must be a number.", "danger")
                return render_template("farmers/form.html", farmer=farmer)

        if not name:
            flash("Name is required.", "danger")
            return render_template("farmers/form.html", farmer=farmer)

        with get_connection() as conn:
            conn.execute(
                """
                UPDATE farmers
                SET name = ?, contact_info = ?, address = ?, contract_status = ?, land_size_ha = ?, lat = ?, lng = ?
                WHERE id = ?
                """,
                (name, contact_info, address, contract_status, land_size_ha, lat, lng, farmer_id),
            )
            conn.commit()

        flash("Farmer updated.", "success")
        return redirect(url_for("farmers.list_farmers"))

    return render_template("farmers/form.html", farmer=farmer)


@bp.post("/<int:farmer_id>/delete")
@login_required
@roles_required("admin", "field_officer")
def delete_farmer(farmer_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM farmers WHERE id = ?", (farmer_id,))
        conn.commit()

    flash("Farmer deleted.", "success")
    return redirect(url_for("farmers.list_farmers"))

