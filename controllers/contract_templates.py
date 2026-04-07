from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from controllers.auth import login_required, roles_required
from models.audit import write_audit_log
from models.db import get_connection


bp = Blueprint("contract_templates", __name__, url_prefix="/contract-templates")


@bp.get("/")
@login_required
@roles_required("admin")
def list_templates():
    with get_connection() as conn:
        templates = conn.execute(
            "SELECT id, name, created_at FROM contract_templates ORDER BY id DESC"
        ).fetchall()
    return render_template("contract_templates/list.html", templates=templates)


@bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_template():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        body = (request.form.get("body") or "").strip()
        if not name or not body:
            flash("Name and body are required.", "danger")
            return render_template("contract_templates/form.html", template=None)

        try:
            with get_connection() as conn:
                cur = conn.execute(
                    "INSERT INTO contract_templates (name, body) VALUES (?, ?)",
                    (name, body),
                )
                template_id = cur.lastrowid
                write_audit_log(
                    conn,
                    user_id=session.get("user_id"),
                    action="create",
                    entity="contract_template",
                    entity_id=template_id,
                    details={"name": name},
                )
                conn.commit()
        except Exception:
            flash("Template name must be unique.", "danger")
            return render_template("contract_templates/form.html", template=None)

        flash("Template created.", "success")
        return redirect(url_for("contract_templates.list_templates"))

    # Basic default skeleton with placeholders
    template = {
        "name": "Standard contract",
        "body": (
            "TOBACCO CONTRACT\n\n"
            "Contract ID: {contract_id}\n"
            "Farmer: {farmer_name}\n"
            "Field Officer: {field_officer_name}\n"
            "Start date: {contract_date}\n"
            "End date: {end_date}\n\n"
            "Terms:\n"
            "- The farmer agrees to follow agronomy guidance.\n"
            "- Deliveries will be recorded per season.\n\n"
            "Signatures:\n"
            "Farmer: ____________________\n"
            "Field Officer: ______________\n"
        ),
    }
    return render_template("contract_templates/form.html", template=template)


@bp.route("/<int:template_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_template(template_id: int):
    with get_connection() as conn:
        template = conn.execute(
            "SELECT id, name, body, created_at FROM contract_templates WHERE id = ?",
            (template_id,),
        ).fetchone()

    if template is None:
        flash("Template not found.", "danger")
        return redirect(url_for("contract_templates.list_templates"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        body = (request.form.get("body") or "").strip()
        if not name or not body:
            flash("Name and body are required.", "danger")
            return render_template("contract_templates/form.html", template=template)

        try:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE contract_templates SET name = ?, body = ? WHERE id = ?",
                    (name, body, template_id),
                )
                write_audit_log(
                    conn,
                    user_id=session.get("user_id"),
                    action="update",
                    entity="contract_template",
                    entity_id=template_id,
                    details={"name": name},
                )
                conn.commit()
        except Exception:
            flash("Template name must be unique.", "danger")
            return render_template("contract_templates/form.html", template=template)

        flash("Template updated.", "success")
        return redirect(url_for("contract_templates.list_templates"))

    return render_template("contract_templates/form.html", template=template)


@bp.post("/<int:template_id>/delete")
@login_required
@roles_required("admin")
def delete_template(template_id: int):
    with get_connection() as conn:
        write_audit_log(
            conn,
            user_id=session.get("user_id"),
            action="delete",
            entity="contract_template",
            entity_id=template_id,
            details={},
        )
        conn.execute("DELETE FROM contract_templates WHERE id = ?", (template_id,))
        conn.commit()

    flash("Template deleted.", "success")
    return redirect(url_for("contract_templates.list_templates"))

