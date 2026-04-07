from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from controllers.auth import login_required, roles_required
from models.audit import write_audit_log
from models.db import get_connection


bp = Blueprint("contract_signatures", __name__, url_prefix="/contracts/<int:contract_id>/signatures")

ALLOWED_SIGNER_ROLES = ["farmer", "field_officer", "company"]


@bp.get("/")
@login_required
@roles_required("admin", "field_officer", "accounts")
def list_signatures(contract_id: int):
    with get_connection() as conn:
        contract = conn.execute(
            """
            SELECT c.id, c.status, f.name AS farmer_name, fo.name AS field_officer_name
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

        signatures = conn.execute(
            """
            SELECT id, signer_role, signer_name, signed_at
            FROM contract_signatures
            WHERE contract_id = ?
            ORDER BY id DESC
            """,
            (contract_id,),
        ).fetchall()

    return render_template(
        "contract_signatures/list.html",
        contract=contract,
        signatures=signatures,
        roles=ALLOWED_SIGNER_ROLES,
    )


@bp.post("/add")
@login_required
@roles_required("admin", "field_officer")
def add_signature(contract_id: int):
    signer_role = (request.form.get("signer_role") or "").strip()
    signer_name = (request.form.get("signer_name") or "").strip()

    if signer_role not in ALLOWED_SIGNER_ROLES:
        flash("Invalid signer role.", "danger")
        return redirect(url_for("contract_signatures.list_signatures", contract_id=contract_id))
    if not signer_name:
        flash("Signer name is required.", "danger")
        return redirect(url_for("contract_signatures.list_signatures", contract_id=contract_id))

    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO contract_signatures (contract_id, signer_role, signer_name)
            VALUES (?, ?, ?)
            """,
            (contract_id, signer_role, signer_name),
        )
        sig_id = cur.lastrowid
        write_audit_log(
            conn,
            user_id=session.get("user_id"),
            action="create",
            entity="contract_signature",
            entity_id=sig_id,
            details={"contract_id": contract_id, "signer_role": signer_role, "signer_name": signer_name},
        )
        conn.commit()

    flash("Signature added.", "success")
    return redirect(url_for("contract_signatures.list_signatures", contract_id=contract_id))


@bp.post("/<int:sig_id>/delete")
@login_required
@roles_required("admin")
def delete_signature(contract_id: int, sig_id: int):
    with get_connection() as conn:
        write_audit_log(
            conn,
            user_id=session.get("user_id"),
            action="delete",
            entity="contract_signature",
            entity_id=sig_id,
            details={"contract_id": contract_id},
        )
        conn.execute(
            "DELETE FROM contract_signatures WHERE id = ? AND contract_id = ?",
            (sig_id, contract_id),
        )
        conn.commit()

    flash("Signature deleted.", "success")
    return redirect(url_for("contract_signatures.list_signatures", contract_id=contract_id))

