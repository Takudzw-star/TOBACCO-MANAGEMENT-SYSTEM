from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from controllers.auth import login_required, roles_required
from models.audit import write_audit_log
from models.db import get_connection


bp = Blueprint("inputs", __name__, url_prefix="/inputs")


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


def _fetch_item_choices():
    with get_connection() as conn:
        items = conn.execute(
            """
            SELECT id, name, category, default_unit, default_unit_cost
            FROM input_items
            WHERE is_active = 1
            ORDER BY category ASC, name ASC
            """
        ).fetchall()
    return items


@bp.get("/")
@login_required
@roles_required("admin", "field_officer", "accounts")
def list_inputs():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
              i.id,
              i.contract_id,
              i.item_id,
              i.item,
              i.quantity,
              i.unit,
              i.unit_cost,
              i.total_cost,
              i.issue_date,
              i.description,
              f.name AS farmer_name,
              fo.name AS field_officer_name
            FROM inputs i
            LEFT JOIN contracts c ON c.id = i.contract_id
            LEFT JOIN farmers f ON f.id = c.farmer_id
            LEFT JOIN field_officers fo ON fo.id = c.field_officer_id
            ORDER BY i.id DESC
            """
        ).fetchall()
    return render_template("inputs/list.html", inputs=rows)


@bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "field_officer", "accounts")
def create_input():
    contracts = _fetch_contract_choices()
    items = _fetch_item_choices()
    return_to = request.args.get("return_to") or request.form.get("return_to")

    if request.method == "POST":
        contract_id = request.form.get("contract_id")
        item_id_raw = (request.form.get("item_id") or "").strip()
        qty_raw = (request.form.get("quantity") or "").strip()
        unit = (request.form.get("unit") or "").strip() or None
        unit_cost_raw = (request.form.get("unit_cost") or "").strip()
        issue_date = (request.form.get("issue_date") or "").strip() or None
        description = (request.form.get("description") or "").strip() or None

        if not contract_id or not item_id_raw:
            flash("Contract and input item are required.", "danger")
            return render_template(
                "inputs/form.html", input_row=None, contracts=contracts, items=items, return_to=return_to
            )

        try:
            quantity = float(qty_raw)
        except ValueError:
            flash("Quantity must be a number.", "danger")
            return render_template(
                "inputs/form.html", input_row=None, contracts=contracts, items=items, return_to=return_to
            )

        unit_cost = None
        if unit_cost_raw:
            try:
                unit_cost = float(unit_cost_raw)
            except ValueError:
                flash("Unit cost must be a number.", "danger")
                return render_template(
                    "inputs/form.html", input_row=None, contracts=contracts, items=items, return_to=return_to
                )

        with get_connection() as conn:
            contract = conn.execute(
                "SELECT id, status FROM contracts WHERE id = ?",
                (int(contract_id),),
            ).fetchone()
            if contract is None:
                flash("Contract not found.", "danger")
                return render_template(
                    "inputs/form.html", input_row=None, contracts=contracts, items=items, return_to=return_to
                )
            if contract["status"] != "active":
                flash("This contract is not active. You cannot issue inputs.", "danger")
                return render_template(
                    "inputs/form.html", input_row=None, contracts=contracts, items=items, return_to=return_to
                )

            item_row = conn.execute(
                "SELECT id, name, default_unit, default_unit_cost FROM input_items WHERE id = ? AND is_active = 1",
                (int(item_id_raw),),
            ).fetchone()
            if item_row is None:
                flash("Input item not found (or inactive).", "danger")
                return render_template(
                    "inputs/form.html", input_row=None, contracts=contracts, items=items, return_to=return_to
                )

            item_name = item_row["name"]
            if not unit:
                unit = item_row["default_unit"]
            if unit_cost is None:
                unit_cost = item_row["default_unit_cost"]

            total_cost = None
            if unit_cost is not None:
                total_cost = float(unit_cost) * float(quantity)

            conn.execute(
                """
                INSERT INTO inputs (contract_id, item_id, item, quantity, unit, unit_cost, total_cost, issue_date, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (int(contract_id), int(item_row["id"]), item_name, quantity, unit, unit_cost, total_cost, issue_date, description),
            )
            input_id = conn.execute("SELECT last_insert_rowid();").fetchone()[0]
            write_audit_log(
                conn,
                user_id=session.get("user_id"),
                action="create",
                entity="input",
                entity_id=input_id,
                details={
                    "contract_id": int(contract_id),
                    "item_id": int(item_row["id"]),
                    "item": item_name,
                    "quantity": quantity,
                    "unit": unit,
                    "unit_cost": unit_cost,
                    "total_cost": total_cost,
                },
            )
            conn.commit()

        flash("Input recorded.", "success")
        return redirect(return_to or url_for("inputs.list_inputs"))

    preselected_contract_id = request.args.get("contract_id", type=int)
    input_row = {"issue_date": date.today().isoformat(), "contract_id": preselected_contract_id}
    return render_template(
        "inputs/form.html", input_row=input_row, contracts=contracts, items=items, return_to=return_to
    )


@bp.route("/<int:input_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin", "field_officer", "accounts")
def edit_input(input_id: int):
    contracts = _fetch_contract_choices()
    items = _fetch_item_choices()
    return_to = request.args.get("return_to") or request.form.get("return_to")

    with get_connection() as conn:
        input_row = conn.execute(
            """
            SELECT id, contract_id, item_id, item, quantity, unit, unit_cost, total_cost, issue_date, description
            FROM inputs
            WHERE id = ?
            """,
            (input_id,),
        ).fetchone()

    if input_row is None:
        flash("Input not found.", "danger")
        return redirect(url_for("inputs.list_inputs"))

    if request.method == "POST":
        contract_id = request.form.get("contract_id")
        item_id_raw = (request.form.get("item_id") or "").strip()
        qty_raw = (request.form.get("quantity") or "").strip()
        unit = (request.form.get("unit") or "").strip() or None
        unit_cost_raw = (request.form.get("unit_cost") or "").strip()
        issue_date = (request.form.get("issue_date") or "").strip() or None
        description = (request.form.get("description") or "").strip() or None

        if not contract_id or not item_id_raw:
            flash("Contract and input item are required.", "danger")
            return render_template(
                "inputs/form.html", input_row=input_row, contracts=contracts, items=items, return_to=return_to
            )

        try:
            quantity = float(qty_raw)
        except ValueError:
            flash("Quantity must be a number.", "danger")
            return render_template(
                "inputs/form.html", input_row=input_row, contracts=contracts, items=items, return_to=return_to
            )

        unit_cost = None
        if unit_cost_raw:
            try:
                unit_cost = float(unit_cost_raw)
            except ValueError:
                flash("Unit cost must be a number.", "danger")
                return render_template(
                    "inputs/form.html", input_row=input_row, contracts=contracts, items=items, return_to=return_to
                )

        with get_connection() as conn:
            item_row = conn.execute(
                "SELECT id, name, default_unit, default_unit_cost FROM input_items WHERE id = ?",
                (int(item_id_raw),),
            ).fetchone()
            if item_row is None:
                flash("Input item not found.", "danger")
                return render_template(
                    "inputs/form.html", input_row=input_row, contracts=contracts, items=items, return_to=return_to
                )

            item_name = item_row["name"]
            if not unit:
                unit = item_row["default_unit"]
            if unit_cost is None:
                unit_cost = item_row["default_unit_cost"]

            total_cost = None
            if unit_cost is not None:
                total_cost = float(unit_cost) * float(quantity)

            conn.execute(
                """
                UPDATE inputs
                SET contract_id = ?, item_id = ?, item = ?, quantity = ?, unit = ?, unit_cost = ?, total_cost = ?, issue_date = ?, description = ?
                WHERE id = ?
                """,
                (
                    int(contract_id),
                    int(item_row["id"]),
                    item_name,
                    quantity,
                    unit,
                    unit_cost,
                    total_cost,
                    issue_date,
                    description,
                    input_id,
                ),
            )
            write_audit_log(
                conn,
                user_id=session.get("user_id"),
                action="update",
                entity="input",
                entity_id=input_id,
                details={
                    "contract_id": int(contract_id),
                    "item_id": int(item_row["id"]),
                    "item": item_name,
                    "quantity": quantity,
                    "unit": unit,
                    "unit_cost": unit_cost,
                    "total_cost": total_cost,
                },
            )
            conn.commit()

        flash("Input updated.", "success")
        return redirect(return_to or url_for("inputs.list_inputs"))

    return render_template(
        "inputs/form.html", input_row=input_row, contracts=contracts, items=items, return_to=return_to
    )


@bp.post("/<int:input_id>/delete")
@login_required
@roles_required("admin", "field_officer", "accounts")
def delete_input(input_id: int):
    return_to = request.args.get("return_to") or request.form.get("return_to")
    with get_connection() as conn:
        write_audit_log(
            conn,
            user_id=session.get("user_id"),
            action="delete",
            entity="input",
            entity_id=input_id,
            details={},
        )
        conn.execute("DELETE FROM inputs WHERE id = ?", (input_id,))
        conn.commit()

    flash("Input deleted.", "success")
    return redirect(return_to or url_for("inputs.list_inputs"))

