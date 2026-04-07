from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from controllers.auth import login_required, roles_required
from models.audit import write_audit_log
from models.db import get_connection


bp = Blueprint("transactions", __name__, url_prefix="/transactions")

ALLOWED_TX_TYPES = ["payment", "advance", "repayment"]


@bp.get("/")
@login_required
@roles_required("admin", "accountant", "manager")
def list_transactions():
    with get_connection() as conn:
        txs = conn.execute(
            """
            SELECT
              t.id,
              t.reference,
              t.tx_type,
              t.amount,
              t.transaction_date,
              t.description,
              t.contract_id,
              f.name AS farmer_name,
              fo.name AS field_officer_name
            FROM transactions t
            LEFT JOIN contracts c ON c.id = t.contract_id
            LEFT JOIN farmers f ON f.id = c.farmer_id
            LEFT JOIN field_officers fo ON fo.id = c.field_officer_id
            ORDER BY t.id DESC
            """
        ).fetchall()
    return render_template("transactions/list.html", transactions=txs)


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


@bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "accountant")
def create_transaction():
    contracts = _fetch_contract_choices()
    return_to = request.args.get("return_to") or request.form.get("return_to")

    if request.method == "POST":
        contract_id = request.form.get("contract_id")
        tx_type = (request.form.get("tx_type") or "").strip() or "payment"
        amount_raw = (request.form.get("amount") or "").strip()
        transaction_date = (request.form.get("transaction_date") or "").strip() or None
        description = (request.form.get("description") or "").strip() or None

        if not contract_id:
            flash("Contract is required.", "danger")
            return render_template(
                "transactions/form.html",
                transaction=None,
                contracts=contracts,
            )

        if tx_type not in ALLOWED_TX_TYPES:
            flash("Invalid transaction type.", "danger")
            return render_template("transactions/form.html", transaction=None, contracts=contracts)

        try:
            amount = float(amount_raw)
        except ValueError:
            flash("Amount must be a number.", "danger")
            return render_template(
                "transactions/form.html",
                transaction=None,
                contracts=contracts,
            )

        with get_connection() as conn:
            contract = conn.execute(
                "SELECT id, status FROM contracts WHERE id = ?",
                (int(contract_id),),
            ).fetchone()
            if contract is None:
                flash("Contract not found.", "danger")
                return render_template("transactions/form.html", transaction=None, contracts=contracts)
            if contract["status"] != "active":
                flash("This contract is not active. You cannot add transactions.", "danger")
                return render_template("transactions/form.html", transaction=None, contracts=contracts)

            cur = conn.execute(
                """
                INSERT INTO transactions (contract_id, tx_type, amount, transaction_date, description)
                VALUES (?, ?, ?, ?, ?)
                """,
                (int(contract_id), tx_type, amount, transaction_date, description),
            )
            tx_id = cur.lastrowid
            reference = f"TX-{date.today().strftime('%Y%m%d')}-{tx_id}"
            conn.execute(
                "UPDATE transactions SET reference = COALESCE(reference, ?) WHERE id = ?",
                (reference, tx_id),
            )
            write_audit_log(
                conn,
                user_id=session.get("user_id"),
                action="create",
                entity="transaction",
                entity_id=tx_id,
                details={
                    "contract_id": int(contract_id),
                    "tx_type": tx_type,
                    "amount": amount,
                    "transaction_date": transaction_date,
                    "reference": reference,
                },
            )
            conn.commit()

        flash("Transaction recorded.", "success")
        return redirect(return_to or url_for("transactions.list_transactions"))

    preselected_contract_id = request.args.get("contract_id", type=int)
    transaction = {
        "transaction_date": date.today().isoformat(),
        "contract_id": preselected_contract_id,
        "tx_type": "payment",
    }
    return render_template(
        "transactions/form.html",
        transaction=transaction,
        contracts=contracts,
        tx_types=ALLOWED_TX_TYPES,
        return_to=return_to,
    )


@bp.route("/<int:transaction_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin", "accountant")
def edit_transaction(transaction_id: int):
    contracts = _fetch_contract_choices()
    return_to = request.args.get("return_to") or request.form.get("return_to")

    with get_connection() as conn:
        tx = conn.execute(
            """
            SELECT id, reference, contract_id, tx_type, amount, transaction_date, description
            FROM transactions
            WHERE id = ?
            """,
            (transaction_id,),
        ).fetchone()

    if tx is None:
        flash("Transaction not found.", "danger")
        return redirect(url_for("transactions.list_transactions"))

    if request.method == "POST":
        contract_id = request.form.get("contract_id")
        tx_type = (request.form.get("tx_type") or "").strip() or "payment"
        amount_raw = (request.form.get("amount") or "").strip()
        transaction_date = (request.form.get("transaction_date") or "").strip() or None
        description = (request.form.get("description") or "").strip() or None

        if not contract_id:
            flash("Contract is required.", "danger")
            return render_template(
                "transactions/form.html",
                transaction=tx,
                contracts=contracts,
            )

        if tx_type not in ALLOWED_TX_TYPES:
            flash("Invalid transaction type.", "danger")
            return render_template("transactions/form.html", transaction=tx, contracts=contracts, tx_types=ALLOWED_TX_TYPES)

        try:
            amount = float(amount_raw)
        except ValueError:
            flash("Amount must be a number.", "danger")
            return render_template(
                "transactions/form.html",
                transaction=tx,
                contracts=contracts,
            )

        with get_connection() as conn:
            conn.execute(
                """
                UPDATE transactions
                SET contract_id = ?, tx_type = ?, amount = ?, transaction_date = ?, description = ?
                WHERE id = ?
                """,
                (int(contract_id), tx_type, amount, transaction_date, description, transaction_id),
            )
            write_audit_log(
                conn,
                user_id=session.get("user_id"),
                action="update",
                entity="transaction",
                entity_id=transaction_id,
                details={
                    "contract_id": int(contract_id),
                    "tx_type": tx_type,
                    "amount": amount,
                    "transaction_date": transaction_date,
                },
            )
            conn.commit()

        flash("Transaction updated.", "success")
        return redirect(return_to or url_for("transactions.list_transactions"))

    return render_template(
        "transactions/form.html",
        transaction=tx,
        contracts=contracts,
        tx_types=ALLOWED_TX_TYPES,
        return_to=return_to,
    )


@bp.post("/<int:transaction_id>/delete")
@login_required
@roles_required("admin", "accountant")
def delete_transaction(transaction_id: int):
    return_to = request.args.get("return_to") or request.form.get("return_to")
    with get_connection() as conn:
        write_audit_log(
            conn,
            user_id=session.get("user_id"),
            action="delete",
            entity="transaction",
            entity_id=transaction_id,
            details={},
        )
        conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
        conn.commit()

    flash("Transaction deleted.", "success")
    return redirect(return_to or url_for("transactions.list_transactions"))


@bp.get("/<int:transaction_id>/receipt")
@login_required
@roles_required("admin", "accountant", "manager")
def transaction_receipt(transaction_id: int):
    with get_connection() as conn:
        tx = conn.execute(
            """
            SELECT
              t.id,
              t.reference,
              t.amount,
              t.transaction_date,
              t.description,
              t.contract_id,
              c.contract_date,
              f.name AS farmer_name,
              f.contact_info AS farmer_contact_info,
              fo.name AS field_officer_name,
              fo.region AS field_officer_region
            FROM transactions t
            LEFT JOIN contracts c ON c.id = t.contract_id
            LEFT JOIN farmers f ON f.id = c.farmer_id
            LEFT JOIN field_officers fo ON fo.id = c.field_officer_id
            WHERE t.id = ?
            """,
            (transaction_id,),
        ).fetchone()

    if tx is None:
        flash("Transaction not found.", "danger")
        return redirect(url_for("transactions.list_transactions"))

    return render_template("transactions/receipt.html", tx=tx)

