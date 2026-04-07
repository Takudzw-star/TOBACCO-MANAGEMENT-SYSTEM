from string import Formatter

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from controllers.auth import login_required, roles_required
from models.audit import write_audit_log
from models.db import get_connection


bp = Blueprint("contract_documents", __name__, url_prefix="/contracts/<int:contract_id>/documents")


def _safe_format(template: str, values: dict):
    # Only allow placeholders that exist in values.
    fmt = Formatter()
    for _, field_name, _, _ in fmt.parse(template):
        if field_name and field_name not in values:
            values[field_name] = ""
    return template.format_map(values)


@bp.get("/")
@login_required
@roles_required("admin", "field_officer", "accounts")
def list_documents(contract_id: int):
    with get_connection() as conn:
        contract = conn.execute(
            """
            SELECT c.id, c.status, c.contract_date, c.end_date, f.name AS farmer_name, fo.name AS field_officer_name
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

        docs = conn.execute(
            """
            SELECT d.id, d.title, d.created_at, t.name AS template_name
            FROM contract_documents d
            LEFT JOIN contract_templates t ON t.id = d.template_id
            WHERE d.contract_id = ?
            ORDER BY d.id DESC
            """,
            (contract_id,),
        ).fetchall()

        templates = conn.execute("SELECT id, name FROM contract_templates ORDER BY name ASC").fetchall()

    return render_template(
        "contract_documents/list.html", contract=contract, documents=docs, templates=templates
    )


@bp.post("/generate")
@login_required
@roles_required("admin", "field_officer")
def generate_document(contract_id: int):
    template_id = request.form.get("template_id")
    title = (request.form.get("title") or "").strip() or None

    if not template_id:
        flash("Select a template.", "danger")
        return redirect(url_for("contract_documents.list_documents", contract_id=contract_id))

    with get_connection() as conn:
        contract = conn.execute(
            """
            SELECT c.id, c.status, c.contract_date, c.end_date, c.details,
                   f.name AS farmer_name, f.contact_info AS farmer_contact,
                   fo.name AS field_officer_name, fo.region AS field_officer_region
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

        tpl = conn.execute(
            "SELECT id, name, body FROM contract_templates WHERE id = ?",
            (int(template_id),),
        ).fetchone()
        if tpl is None:
            flash("Template not found.", "danger")
            return redirect(url_for("contract_documents.list_documents", contract_id=contract_id))

        values = {
            "contract_id": contract["id"],
            "status": contract["status"],
            "contract_date": contract["contract_date"] or "",
            "end_date": contract["end_date"] or "",
            "details": contract["details"] or "",
            "farmer_name": contract["farmer_name"] or "",
            "farmer_contact": contract["farmer_contact"] or "",
            "field_officer_name": contract["field_officer_name"] or "",
            "field_officer_region": contract["field_officer_region"] or "",
        }

        rendered = _safe_format(tpl["body"], values)
        doc_title = title or f"{tpl['name']} · Contract #{contract_id}"

        cur = conn.execute(
            """
            INSERT INTO contract_documents (contract_id, template_id, title, body)
            VALUES (?, ?, ?, ?)
            """,
            (contract_id, tpl["id"], doc_title, rendered),
        )
        doc_id = cur.lastrowid
        write_audit_log(
            conn,
            user_id=session.get("user_id"),
            action="create",
            entity="contract_document",
            entity_id=doc_id,
            details={"contract_id": contract_id, "template_id": tpl["id"], "title": doc_title},
        )
        conn.commit()

    flash("Document generated.", "success")
    return redirect(url_for("contract_documents.view_document", contract_id=contract_id, doc_id=doc_id))


@bp.get("/<int:doc_id>")
@login_required
@roles_required("admin", "field_officer", "accounts")
def view_document(contract_id: int, doc_id: int):
    with get_connection() as conn:
        doc = conn.execute(
            """
            SELECT d.id, d.title, d.body, d.created_at, t.name AS template_name
            FROM contract_documents d
            LEFT JOIN contract_templates t ON t.id = d.template_id
            WHERE d.id = ? AND d.contract_id = ?
            """,
            (doc_id, contract_id),
        ).fetchone()
        if doc is None:
            flash("Document not found.", "danger")
            return redirect(url_for("contract_documents.list_documents", contract_id=contract_id))

        signatures = conn.execute(
            """
            SELECT signer_role, signer_name, signed_at
            FROM contract_signatures
            WHERE contract_id = ?
            ORDER BY signed_at DESC
            """,
            (contract_id,),
        ).fetchall()

    return render_template(
        "contract_documents/view.html", contract_id=contract_id, doc=doc, signatures=signatures
    )


@bp.post("/<int:doc_id>/delete")
@login_required
@roles_required("admin")
def delete_document(contract_id: int, doc_id: int):
    with get_connection() as conn:
        write_audit_log(
            conn,
            user_id=session.get("user_id"),
            action="delete",
            entity="contract_document",
            entity_id=doc_id,
            details={"contract_id": contract_id},
        )
        conn.execute("DELETE FROM contract_documents WHERE id = ? AND contract_id = ?", (doc_id, contract_id))
        conn.commit()

    flash("Document deleted.", "success")
    return redirect(url_for("contract_documents.list_documents", contract_id=contract_id))

