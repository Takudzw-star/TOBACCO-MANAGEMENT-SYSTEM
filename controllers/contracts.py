from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from controllers.auth import login_required, roles_required
from models.audit import write_audit_log
from models.db import get_connection


bp = Blueprint("contracts", __name__, url_prefix="/contracts")

ALLOWED_STATUSES = ["draft", "active", "completed", "terminated"]


@bp.get("/")
@login_required
@roles_required("admin", "field_officer")
def list_contracts():
    with get_connection() as conn:
        contracts = conn.execute(
            """
            SELECT
              c.id,
              c.status,
              c.contract_date,
              c.end_date,
              c.details,
              f.id AS farmer_id,
              f.name AS farmer_name,
              fo.id AS field_officer_id,
              fo.name AS field_officer_name,
              fo.region AS field_officer_region
            FROM contracts c
            LEFT JOIN farmers f ON f.id = c.farmer_id
            LEFT JOIN field_officers fo ON fo.id = c.field_officer_id
            ORDER BY c.id DESC
            """
        ).fetchall()
    return render_template("contracts/list.html", contracts=contracts)


@bp.get("/<int:contract_id>")
@login_required
@roles_required("admin", "field_officer", "accounts")
def contract_detail(contract_id: int):
    with get_connection() as conn:
        contract = conn.execute(
            """
            SELECT
              c.id,
              c.status,
              c.contract_date,
              c.end_date,
              c.details,
              f.id AS farmer_id,
              f.name AS farmer_name,
              f.contact_info AS farmer_contact_info,
              f.address AS farmer_address,
              fo.id AS field_officer_id,
              fo.name AS field_officer_name,
              fo.region AS field_officer_region,
              fo.contact_info AS field_officer_contact_info
            FROM contracts c
            LEFT JOIN farmers f ON f.id = c.farmer_id
            LEFT JOIN field_officers fo ON fo.id = c.field_officer_id
            WHERE c.id = ?
            """,
            (contract_id,),
        ).fetchone()

        if contract is None:
            flash("Contract not found.", "danger")
            return redirect(url_for("contracts.list_contracts"))

        transactions = conn.execute(
            """
            SELECT id, amount, transaction_date, description
            FROM transactions
            WHERE contract_id = ?
            ORDER BY id DESC
            """,
            (contract_id,),
        ).fetchall()

        inputs_issued = conn.execute(
            """
            SELECT id, item, quantity, unit, issue_date, description
            FROM inputs
            WHERE contract_id = ?
            ORDER BY id DESC
            """,
            (contract_id,),
        ).fetchall()

        yield_deliveries = conn.execute(
            """
            SELECT id, season, grade, weight_kg, delivery_date, notes
            FROM yields
            WHERE contract_id = ?
            ORDER BY delivery_date DESC, id DESC
            """,
            (contract_id,),
        ).fetchall()

        signatures = conn.execute(
            """
            SELECT signer_role, signer_name, signed_at
            FROM contract_signatures
            WHERE contract_id = ?
            ORDER BY signed_at DESC
            """,
            (contract_id,),
        ).fetchall()

    total_amount = sum((t["amount"] or 0) for t in transactions)
    total_yield_kg = sum((y["weight_kg"] or 0) for y in yield_deliveries)
    return render_template(
        "contracts/detail.html",
        contract=contract,
        transactions=transactions,
        inputs_issued=inputs_issued,
        yield_deliveries=yield_deliveries,
        signatures=signatures,
        total_amount=total_amount,
        total_yield_kg=total_yield_kg,
    )


@bp.post("/<int:contract_id>/status")
@login_required
@roles_required("admin", "field_officer")
def update_contract_status(contract_id: int):
    new_status = (request.form.get("status") or "").strip()
    if new_status not in ALLOWED_STATUSES:
        flash("Invalid status.", "danger")
        return redirect(url_for("contracts.contract_detail", contract_id=contract_id))

    user_id = session.get("user_id")
    with get_connection() as conn:
        current = conn.execute("SELECT id, status FROM contracts WHERE id = ?", (contract_id,)).fetchone()
        if current is None:
            flash("Contract not found.", "danger")
            return redirect(url_for("contracts.list_contracts"))

        # Simple transition rules
        cur_status = current["status"] or "active"
        allowed = {
            "draft": {"active", "terminated"},
            "active": {"completed", "terminated"},
            "completed": set(),
            "terminated": set(),
        }
        if new_status != cur_status and new_status not in allowed.get(cur_status, set()):
            flash(f"Cannot change status from {cur_status} to {new_status}.", "danger")
            return redirect(url_for("contracts.contract_detail", contract_id=contract_id))

        conn.execute("UPDATE contracts SET status = ? WHERE id = ?", (new_status, contract_id))
        write_audit_log(
            conn,
            user_id=user_id,
            action="update",
            entity="contract",
            entity_id=contract_id,
            details={"status_from": cur_status, "status_to": new_status},
        )
        conn.commit()

    flash("Contract status updated.", "success")
    return redirect(url_for("contracts.contract_detail", contract_id=contract_id))


def _fetch_form_choices():
    with get_connection() as conn:
        farmers = conn.execute("SELECT id, name FROM farmers ORDER BY name ASC").fetchall()
        officers = conn.execute(
            "SELECT id, name, region FROM field_officers ORDER BY name ASC"
        ).fetchall()
    return farmers, officers


@bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "field_officer")
def create_contract():
    farmers, officers = _fetch_form_choices()

    if request.method == "POST":
        farmer_id = request.form.get("farmer_id")
        field_officer_id = request.form.get("field_officer_id")
        contract_date = (request.form.get("contract_date") or "").strip() or None
        end_date = (request.form.get("end_date") or "").strip() or None
        details = (request.form.get("details") or "").strip() or None

        if not farmer_id or not field_officer_id:
            flash("Farmer and Field Officer are required.", "danger")
            return render_template(
                "contracts/form.html",
                contract=None,
                farmers=farmers,
                officers=officers,
            )

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO contracts (farmer_id, field_officer_id, status, contract_date, end_date, details)
                VALUES (?, ?, 'draft', ?, ?, ?)
                """,
                (int(farmer_id), int(field_officer_id), contract_date, end_date, details),
            )
            conn.commit()

        flash("Contract created.", "success")
        return redirect(url_for("contracts.list_contracts"))

    contract = {"contract_date": date.today().isoformat()}
    return render_template(
        "contracts/form.html",
        contract=contract,
        farmers=farmers,
        officers=officers,
    )


@bp.route("/<int:contract_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin", "field_officer")
def edit_contract(contract_id: int):
    farmers, officers = _fetch_form_choices()

    with get_connection() as conn:
        contract = conn.execute(
            """
            SELECT id, status, farmer_id, field_officer_id, contract_date, end_date, details
            FROM contracts
            WHERE id = ?
            """,
            (contract_id,),
        ).fetchone()

    if contract is None:
        flash("Contract not found.", "danger")
        return redirect(url_for("contracts.list_contracts"))

    if request.method == "POST":
        if contract["status"] in ("completed", "terminated"):
            flash("This contract is locked and cannot be edited.", "danger")
            return redirect(url_for("contracts.contract_detail", contract_id=contract_id))

        farmer_id = request.form.get("farmer_id")
        field_officer_id = request.form.get("field_officer_id")
        contract_date = (request.form.get("contract_date") or "").strip() or None
        end_date = (request.form.get("end_date") or "").strip() or None
        details = (request.form.get("details") or "").strip() or None

        if not farmer_id or not field_officer_id:
            flash("Farmer and Field Officer are required.", "danger")
            return render_template(
                "contracts/form.html",
                contract=contract,
                farmers=farmers,
                officers=officers,
            )

        with get_connection() as conn:
            conn.execute(
                """
                UPDATE contracts
                SET farmer_id = ?, field_officer_id = ?, contract_date = ?, end_date = ?, details = ?
                WHERE id = ?
                """,
                (int(farmer_id), int(field_officer_id), contract_date, end_date, details, contract_id),
            )
            conn.commit()

        flash("Contract updated.", "success")
        return redirect(url_for("contracts.list_contracts"))

    return render_template(
        "contracts/form.html",
        contract=contract,
        farmers=farmers,
        officers=officers,
    )


@bp.post("/<int:contract_id>/delete")
@login_required
@roles_required("admin", "field_officer")
def delete_contract(contract_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM contracts WHERE id = ?", (contract_id,))
        conn.commit()

    flash("Contract deleted.", "success")
    return redirect(url_for("contracts.list_contracts"))

