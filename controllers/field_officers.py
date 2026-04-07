from flask import Blueprint, flash, redirect, render_template, request, url_for

from controllers.auth import login_required, roles_required
from models.db import get_connection


bp = Blueprint("field_officers", __name__, url_prefix="/field-officers")


@bp.get("/")
@login_required
@roles_required("admin", "field_officer")
def list_field_officers():
    with get_connection() as conn:
        officers = conn.execute(
            "SELECT id, name, region, contact_info FROM field_officers ORDER BY id DESC"
        ).fetchall()
    return render_template("field_officers/list.html", officers=officers)


@bp.get("/<int:officer_id>")
@login_required
@roles_required("admin", "field_officer")
def field_officer_detail(officer_id: int):
    with get_connection() as conn:
        officer = conn.execute(
            "SELECT id, name, region, contact_info FROM field_officers WHERE id = ?",
            (officer_id,),
        ).fetchone()

        if officer is None:
            flash("Field officer not found.", "danger")
            return redirect(url_for("field_officers.list_field_officers"))

        contracts = conn.execute(
            """
            SELECT
              c.id AS contract_id,
              c.contract_date,
              c.details,
              f.id AS farmer_id,
              f.name AS farmer_name,
              COALESCE(SUM(t.amount), 0) AS total_paid,
              MAX(t.transaction_date) AS last_payment_date
            FROM contracts c
            LEFT JOIN farmers f ON f.id = c.farmer_id
            LEFT JOIN transactions t ON t.contract_id = c.id
            WHERE c.field_officer_id = ?
            GROUP BY c.id, c.contract_date, c.details, f.id, f.name
            ORDER BY c.id DESC
            """,
            (officer_id,),
        ).fetchall()

        totals = conn.execute(
            """
            SELECT
              COALESCE(SUM(t.amount), 0) AS total_paid,
              COUNT(DISTINCT c.id) AS contract_count,
              COUNT(DISTINCT c.farmer_id) AS farmer_count,
              MAX(t.transaction_date) AS last_payment_date
            FROM field_officers fo
            LEFT JOIN contracts c ON c.field_officer_id = fo.id
            LEFT JOIN transactions t ON t.contract_id = c.id
            WHERE fo.id = ?
            """,
            (officer_id,),
        ).fetchone()

    return render_template(
        "field_officers/detail.html",
        officer=officer,
        contracts=contracts,
        totals=totals,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "field_officer")
def create_field_officer():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        region = (request.form.get("region") or "").strip() or None
        contact_info = (request.form.get("contact_info") or "").strip() or None

        if not name:
            flash("Name is required.", "danger")
            return render_template("field_officers/form.html", officer=None)

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO field_officers (name, region, contact_info) VALUES (?, ?, ?)",
                (name, region, contact_info),
            )
            conn.commit()

        flash("Field officer created.", "success")
        return redirect(url_for("field_officers.list_field_officers"))

    return render_template("field_officers/form.html", officer=None)


@bp.route("/<int:officer_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin", "field_officer")
def edit_field_officer(officer_id: int):
    with get_connection() as conn:
        officer = conn.execute(
            "SELECT id, name, region, contact_info FROM field_officers WHERE id = ?",
            (officer_id,),
        ).fetchone()

    if officer is None:
        flash("Field officer not found.", "danger")
        return redirect(url_for("field_officers.list_field_officers"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        region = (request.form.get("region") or "").strip() or None
        contact_info = (request.form.get("contact_info") or "").strip() or None

        if not name:
            flash("Name is required.", "danger")
            return render_template("field_officers/form.html", officer=officer)

        with get_connection() as conn:
            conn.execute(
                """
                UPDATE field_officers
                SET name = ?, region = ?, contact_info = ?
                WHERE id = ?
                """,
                (name, region, contact_info, officer_id),
            )
            conn.commit()

        flash("Field officer updated.", "success")
        return redirect(url_for("field_officers.list_field_officers"))

    return render_template("field_officers/form.html", officer=officer)


@bp.post("/<int:officer_id>/delete")
@login_required
@roles_required("admin", "field_officer")
def delete_field_officer(officer_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM field_officers WHERE id = ?", (officer_id,))
        conn.commit()

    flash("Field officer deleted.", "success")
    return redirect(url_for("field_officers.list_field_officers"))

