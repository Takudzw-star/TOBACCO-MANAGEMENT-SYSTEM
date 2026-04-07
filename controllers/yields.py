from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from controllers.auth import login_required, roles_required
from models.audit import write_audit_log
from models.db import get_connection


bp = Blueprint("yields", __name__, url_prefix="/yields")


def _fetch_contract_choices():
    with get_connection() as conn:
        contracts = conn.execute(
            """
            SELECT
              c.id,
              c.contract_date,
              f.name AS farmer_name,
              fo.name AS field_officer_name
            FROM contracts c
            LEFT JOIN farmers f ON f.id = c.farmer_id
            LEFT JOIN field_officers fo ON fo.id = c.field_officer_id
            ORDER BY c.id DESC
            """
        ).fetchall()
    return contracts


@bp.get("/")
@login_required
@roles_required("admin", "field_officer")
def list_yields():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
              y.id,
              y.contract_id,
              y.season,
              y.grade,
              y.weight_kg,
              y.delivery_date,
              y.notes,
              f.name AS farmer_name,
              fo.name AS field_officer_name
            FROM yields y
            LEFT JOIN contracts c ON c.id = y.contract_id
            LEFT JOIN farmers f ON f.id = c.farmer_id
            LEFT JOIN field_officers fo ON fo.id = c.field_officer_id
            ORDER BY y.delivery_date DESC, y.id DESC
            """
        ).fetchall()
    return render_template("yields/list.html", yields=rows)


@bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "field_officer")
def create_yield():
    contracts = _fetch_contract_choices()
    return_to = request.args.get("return_to") or request.form.get("return_to")

    if request.method == "POST":
        contract_id = request.form.get("contract_id")
        season = (request.form.get("season") or "").strip()
        grade = (request.form.get("grade") or "").strip() or None
        weight_raw = (request.form.get("weight_kg") or "").strip()
        delivery_date = (request.form.get("delivery_date") or "").strip()
        notes = (request.form.get("notes") or "").strip() or None

        if not contract_id or not season or not delivery_date:
            flash("Contract, season, and delivery date are required.", "danger")
            return render_template("yields/form.html", row=None, contracts=contracts, return_to=return_to)

        try:
            weight_kg = float(weight_raw)
        except ValueError:
            flash("Weight must be a number (kg).", "danger")
            return render_template("yields/form.html", row=None, contracts=contracts, return_to=return_to)

        if weight_kg <= 0:
            flash("Weight must be greater than 0.", "danger")
            return render_template("yields/form.html", row=None, contracts=contracts, return_to=return_to)

        with get_connection() as conn:
            contract = conn.execute("SELECT id, status FROM contracts WHERE id = ?", (int(contract_id),)).fetchone()
            if contract is None:
                flash("Contract not found.", "danger")
                return render_template("yields/form.html", row=None, contracts=contracts, return_to=return_to)
            if contract["status"] != "active":
                flash("This contract is not active. You cannot record yields.", "danger")
                return render_template("yields/form.html", row=None, contracts=contracts, return_to=return_to)

            cur = conn.execute(
                """
                INSERT INTO yields (contract_id, season, grade, weight_kg, delivery_date, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (int(contract_id), season, grade, weight_kg, delivery_date, notes),
            )
            yield_id = cur.lastrowid
            write_audit_log(
                conn,
                user_id=session.get("user_id"),
                action="create",
                entity="yield",
                entity_id=yield_id,
                details={"contract_id": int(contract_id), "season": season, "grade": grade, "weight_kg": weight_kg},
            )
            conn.commit()

        flash("Yield recorded.", "success")
        return redirect(return_to or url_for("yields.list_yields"))

    row = {"delivery_date": date.today().isoformat(), "contract_id": request.args.get("contract_id", type=int)}
    return render_template("yields/form.html", row=row, contracts=contracts, return_to=return_to)


@bp.route("/<int:yield_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin", "field_officer")
def edit_yield(yield_id: int):
    contracts = _fetch_contract_choices()
    return_to = request.args.get("return_to") or request.form.get("return_to")

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, contract_id, season, grade, weight_kg, delivery_date, notes
            FROM yields
            WHERE id = ?
            """,
            (yield_id,),
        ).fetchone()

    if row is None:
        flash("Yield record not found.", "danger")
        return redirect(url_for("yields.list_yields"))

    if request.method == "POST":
        contract_id = request.form.get("contract_id")
        season = (request.form.get("season") or "").strip()
        grade = (request.form.get("grade") or "").strip() or None
        weight_raw = (request.form.get("weight_kg") or "").strip()
        delivery_date = (request.form.get("delivery_date") or "").strip()
        notes = (request.form.get("notes") or "").strip() or None

        if not contract_id or not season or not delivery_date:
            flash("Contract, season, and delivery date are required.", "danger")
            return render_template("yields/form.html", row=row, contracts=contracts, return_to=return_to)

        try:
            weight_kg = float(weight_raw)
        except ValueError:
            flash("Weight must be a number (kg).", "danger")
            return render_template("yields/form.html", row=row, contracts=contracts, return_to=return_to)

        if weight_kg <= 0:
            flash("Weight must be greater than 0.", "danger")
            return render_template("yields/form.html", row=row, contracts=contracts, return_to=return_to)

        with get_connection() as conn:
            contract = conn.execute("SELECT id, status FROM contracts WHERE id = ?", (int(contract_id),)).fetchone()
            if contract is None:
                flash("Contract not found.", "danger")
                return render_template("yields/form.html", row=row, contracts=contracts, return_to=return_to)
            if contract["status"] != "active":
                flash("This contract is not active. You cannot edit yields.", "danger")
                return render_template("yields/form.html", row=row, contracts=contracts, return_to=return_to)

            conn.execute(
                """
                UPDATE yields
                SET contract_id = ?, season = ?, grade = ?, weight_kg = ?, delivery_date = ?, notes = ?
                WHERE id = ?
                """,
                (int(contract_id), season, grade, weight_kg, delivery_date, notes, yield_id),
            )
            write_audit_log(
                conn,
                user_id=session.get("user_id"),
                action="update",
                entity="yield",
                entity_id=yield_id,
                details={"contract_id": int(contract_id), "season": season, "grade": grade, "weight_kg": weight_kg},
            )
            conn.commit()

        flash("Yield updated.", "success")
        return redirect(return_to or url_for("yields.list_yields"))

    return render_template("yields/form.html", row=row, contracts=contracts, return_to=return_to)


@bp.post("/<int:yield_id>/delete")
@login_required
@roles_required("admin", "field_officer")
def delete_yield(yield_id: int):
    return_to = request.args.get("return_to") or request.form.get("return_to")
    with get_connection() as conn:
        write_audit_log(
            conn,
            user_id=session.get("user_id"),
            action="delete",
            entity="yield",
            entity_id=yield_id,
            details={},
        )
        conn.execute("DELETE FROM yields WHERE id = ?", (yield_id,))
        conn.commit()

    flash("Yield deleted.", "success")
    return redirect(return_to or url_for("yields.list_yields"))

