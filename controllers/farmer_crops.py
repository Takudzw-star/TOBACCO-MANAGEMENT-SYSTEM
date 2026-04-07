from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from controllers.auth import login_required, roles_required
from models.audit import write_audit_log
from models.db import get_connection


bp = Blueprint("farmer_crops", __name__, url_prefix="/farmers/<int:farmer_id>/crops")


@bp.get("/")
@login_required
@roles_required("admin", "field_officer")
def list_crops(farmer_id: int):
    with get_connection() as conn:
        farmer = conn.execute("SELECT id, name FROM farmers WHERE id = ?", (farmer_id,)).fetchone()
        if farmer is None:
            flash("Farmer not found.", "danger")
            return redirect(url_for("farmers.list_farmers"))

        crops = conn.execute(
            """
            SELECT id, season, crop, area_ha, notes
            FROM farmer_crops
            WHERE farmer_id = ?
            ORDER BY season DESC, id DESC
            """,
            (farmer_id,),
        ).fetchall()

    return render_template("farmer_crops/list.html", farmer=farmer, crops=crops)


@bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "field_officer")
def create_crop(farmer_id: int):
    with get_connection() as conn:
        farmer = conn.execute("SELECT id, name FROM farmers WHERE id = ?", (farmer_id,)).fetchone()
    if farmer is None:
        flash("Farmer not found.", "danger")
        return redirect(url_for("farmers.list_farmers"))

    if request.method == "POST":
        season = (request.form.get("season") or "").strip()
        crop = (request.form.get("crop") or "").strip()
        area_raw = (request.form.get("area_ha") or "").strip()
        notes = (request.form.get("notes") or "").strip() or None

        area_ha = None
        if area_raw:
            try:
                area_ha = float(area_raw)
            except ValueError:
                flash("Area must be a number (ha).", "danger")
                return render_template("farmer_crops/form.html", farmer=farmer, row=None)

        if not season or not crop:
            flash("Season and crop are required.", "danger")
            return render_template("farmer_crops/form.html", farmer=farmer, row=None)

        with get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO farmer_crops (farmer_id, season, crop, area_ha, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (farmer_id, season, crop, area_ha, notes),
            )
            crop_id = cur.lastrowid
            write_audit_log(
                conn,
                user_id=session.get("user_id"),
                action="create",
                entity="farmer_crop",
                entity_id=crop_id,
                details={"farmer_id": farmer_id, "season": season, "crop": crop, "area_ha": area_ha},
            )
            conn.commit()

        flash("Crop history added.", "success")
        return redirect(url_for("farmer_crops.list_crops", farmer_id=farmer_id))

    return render_template("farmer_crops/form.html", farmer=farmer, row=None)


@bp.route("/<int:crop_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin", "field_officer")
def edit_crop(farmer_id: int, crop_id: int):
    with get_connection() as conn:
        farmer = conn.execute("SELECT id, name FROM farmers WHERE id = ?", (farmer_id,)).fetchone()
        row = conn.execute(
            "SELECT id, season, crop, area_ha, notes FROM farmer_crops WHERE id = ? AND farmer_id = ?",
            (crop_id, farmer_id),
        ).fetchone()

    if farmer is None:
        flash("Farmer not found.", "danger")
        return redirect(url_for("farmers.list_farmers"))
    if row is None:
        flash("Crop history record not found.", "danger")
        return redirect(url_for("farmer_crops.list_crops", farmer_id=farmer_id))

    if request.method == "POST":
        season = (request.form.get("season") or "").strip()
        crop = (request.form.get("crop") or "").strip()
        area_raw = (request.form.get("area_ha") or "").strip()
        notes = (request.form.get("notes") or "").strip() or None

        area_ha = None
        if area_raw:
            try:
                area_ha = float(area_raw)
            except ValueError:
                flash("Area must be a number (ha).", "danger")
                return render_template("farmer_crops/form.html", farmer=farmer, row=row)

        if not season or not crop:
            flash("Season and crop are required.", "danger")
            return render_template("farmer_crops/form.html", farmer=farmer, row=row)

        with get_connection() as conn:
            conn.execute(
                """
                UPDATE farmer_crops
                SET season = ?, crop = ?, area_ha = ?, notes = ?
                WHERE id = ? AND farmer_id = ?
                """,
                (season, crop, area_ha, notes, crop_id, farmer_id),
            )
            write_audit_log(
                conn,
                user_id=session.get("user_id"),
                action="update",
                entity="farmer_crop",
                entity_id=crop_id,
                details={"farmer_id": farmer_id, "season": season, "crop": crop, "area_ha": area_ha},
            )
            conn.commit()

        flash("Crop history updated.", "success")
        return redirect(url_for("farmer_crops.list_crops", farmer_id=farmer_id))

    return render_template("farmer_crops/form.html", farmer=farmer, row=row)


@bp.post("/<int:crop_id>/delete")
@login_required
@roles_required("admin", "field_officer")
def delete_crop(farmer_id: int, crop_id: int):
    with get_connection() as conn:
        write_audit_log(
            conn,
            user_id=session.get("user_id"),
            action="delete",
            entity="farmer_crop",
            entity_id=crop_id,
            details={"farmer_id": farmer_id},
        )
        conn.execute("DELETE FROM farmer_crops WHERE id = ? AND farmer_id = ?", (crop_id, farmer_id))
        conn.commit()

    flash("Crop history deleted.", "success")
    return redirect(url_for("farmer_crops.list_crops", farmer_id=farmer_id))

