from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from controllers.auth import login_required, roles_required
from models.audit import write_audit_log
from models.db import get_connection


bp = Blueprint("input_items", __name__, url_prefix="/input-items")

ALLOWED_CATEGORIES = ["Seeds", "Fertilizer", "Pesticide", "Other"]


@bp.get("/")
@login_required
@roles_required("admin", "accounts", "field_officer")
def list_items():
    with get_connection() as conn:
        items = conn.execute(
            """
            SELECT id, name, category, default_unit, default_unit_cost, is_active, created_at
            FROM input_items
            ORDER BY category ASC, name ASC
            """
        ).fetchall()
    return render_template("input_items/list.html", items=items)


@bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "accounts")
def create_item():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        category = (request.form.get("category") or "").strip()
        default_unit = (request.form.get("default_unit") or "").strip() or None
        cost_raw = (request.form.get("default_unit_cost") or "").strip()
        is_active = 1 if request.form.get("is_active") == "on" else 0

        if not name or category not in ALLOWED_CATEGORIES:
            flash("Name and valid category are required.", "danger")
            return render_template("input_items/form.html", item=None, categories=ALLOWED_CATEGORIES)

        default_unit_cost = None
        if cost_raw:
            try:
                default_unit_cost = float(cost_raw)
            except ValueError:
                flash("Default unit cost must be a number.", "danger")
                return render_template("input_items/form.html", item=None, categories=ALLOWED_CATEGORIES)

        try:
            with get_connection() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO input_items (name, category, default_unit, default_unit_cost, is_active)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (name, category, default_unit, default_unit_cost, is_active),
                )
                item_id = cur.lastrowid
                write_audit_log(
                    conn,
                    user_id=session.get("user_id"),
                    action="create",
                    entity="input_item",
                    entity_id=item_id,
                    details={"name": name, "category": category, "default_unit": default_unit},
                )
                conn.commit()
        except Exception:
            flash("Item name must be unique.", "danger")
            return render_template("input_items/form.html", item=None, categories=ALLOWED_CATEGORIES)

        flash("Input item created.", "success")
        return redirect(url_for("input_items.list_items"))

    return render_template("input_items/form.html", item=None, categories=ALLOWED_CATEGORIES)


@bp.route("/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin", "accounts")
def edit_item(item_id: int):
    with get_connection() as conn:
        item = conn.execute(
            """
            SELECT id, name, category, default_unit, default_unit_cost, is_active
            FROM input_items
            WHERE id = ?
            """,
            (item_id,),
        ).fetchone()

    if item is None:
        flash("Item not found.", "danger")
        return redirect(url_for("input_items.list_items"))

    if request.method == "POST":
        category = (request.form.get("category") or "").strip()
        default_unit = (request.form.get("default_unit") or "").strip() or None
        cost_raw = (request.form.get("default_unit_cost") or "").strip()
        is_active = 1 if request.form.get("is_active") == "on" else 0

        if category not in ALLOWED_CATEGORIES:
            flash("Valid category is required.", "danger")
            return render_template("input_items/form.html", item=item, categories=ALLOWED_CATEGORIES)

        default_unit_cost = None
        if cost_raw:
            try:
                default_unit_cost = float(cost_raw)
            except ValueError:
                flash("Default unit cost must be a number.", "danger")
                return render_template("input_items/form.html", item=item, categories=ALLOWED_CATEGORIES)

        with get_connection() as conn:
            conn.execute(
                """
                UPDATE input_items
                SET category = ?, default_unit = ?, default_unit_cost = ?, is_active = ?
                WHERE id = ?
                """,
                (category, default_unit, default_unit_cost, is_active, item_id),
            )
            write_audit_log(
                conn,
                user_id=session.get("user_id"),
                action="update",
                entity="input_item",
                entity_id=item_id,
                details={"category": category, "default_unit": default_unit, "default_unit_cost": default_unit_cost},
            )
            conn.commit()

        flash("Input item updated.", "success")
        return redirect(url_for("input_items.list_items"))

    return render_template("input_items/form.html", item=item, categories=ALLOWED_CATEGORIES)

