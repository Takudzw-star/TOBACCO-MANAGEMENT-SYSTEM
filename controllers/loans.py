from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from controllers.auth import login_required, roles_required
from models.audit import write_audit_log
from models.db import get_connection


bp = Blueprint("loans", __name__, url_prefix="/loans")


def _choices():
    with get_connection() as conn:
        farmers = conn.execute("SELECT id, name FROM farmers ORDER BY name ASC;").fetchall()
        contracts = conn.execute(
            """
            SELECT c.id, c.status, f.name AS farmer_name
            FROM contracts c
            LEFT JOIN farmers f ON f.id = c.farmer_id
            ORDER BY c.id DESC
            """
        ).fetchall()
    return farmers, contracts


@bp.get("/")
@login_required
@roles_required("admin", "accountant", "manager")
def list_loans():
    with get_connection() as conn:
        loans = conn.execute(
            """
            SELECT
              l.id,
              l.farmer_id,
              f.name AS farmer_name,
              l.contract_id,
              l.loan_date,
              l.principal,
              l.status,
              COALESCE(SUM(r.amount), 0) AS repaid_amount
            FROM farmer_loans l
            LEFT JOIN farmers f ON f.id = l.farmer_id
            LEFT JOIN loan_repayments r ON r.loan_id = l.id
            GROUP BY l.id, l.farmer_id, f.name, l.contract_id, l.loan_date, l.principal, l.status
            ORDER BY date(l.loan_date) DESC, l.id DESC
            """
        ).fetchall()

    rows = []
    for l in loans:
        principal = float(l["principal"] or 0)
        repaid = float(l["repaid_amount"] or 0)
        balance = principal - repaid
        rows.append(
            {
                "id": int(l["id"]),
                "farmer_id": int(l["farmer_id"]),
                "farmer_name": l["farmer_name"],
                "contract_id": l["contract_id"],
                "loan_date": l["loan_date"],
                "principal": principal,
                "repaid_amount": repaid,
                "balance": balance,
                "status": l["status"],
            }
        )

    return render_template("loans/list.html", loans=rows)


@bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "accountant")
def create_loan():
    farmers, contracts = _choices()
    if request.method == "POST":
        farmer_id = request.form.get("farmer_id")
        contract_id_raw = (request.form.get("contract_id") or "").strip()
        loan_date = (request.form.get("loan_date") or "").strip() or None
        principal_raw = (request.form.get("principal") or "").strip()
        description = (request.form.get("description") or "").strip() or None

        if not farmer_id:
            flash("Farmer is required.", "danger")
            return render_template("loans/form.html", loan=None, farmers=farmers, contracts=contracts)
        if not loan_date:
            loan_date = date.today().isoformat()

        try:
            principal = float(principal_raw)
        except ValueError:
            flash("Principal must be a number.", "danger")
            return render_template("loans/form.html", loan=None, farmers=farmers, contracts=contracts)
        if principal <= 0:
            flash("Principal must be greater than 0.", "danger")
            return render_template("loans/form.html", loan=None, farmers=farmers, contracts=contracts)

        contract_id = int(contract_id_raw) if contract_id_raw else None

        with get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO farmer_loans (farmer_id, contract_id, loan_date, principal, description, status)
                VALUES (?, ?, ?, ?, ?, 'open')
                """,
                (int(farmer_id), contract_id, loan_date, principal, description),
            )
            loan_id = cur.lastrowid
            write_audit_log(
                conn,
                user_id=session.get("user_id"),
                action="create",
                entity="loan",
                entity_id=loan_id,
                details={"farmer_id": int(farmer_id), "contract_id": contract_id, "principal": principal, "loan_date": loan_date},
            )
            conn.commit()

        flash("Loan/advance created.", "success")
        return redirect(url_for("loans.list_loans"))

    loan = {"loan_date": date.today().isoformat()}
    return render_template("loans/form.html", loan=loan, farmers=farmers, contracts=contracts)


@bp.get("/<int:loan_id>")
@login_required
@roles_required("admin", "accountant", "manager")
def loan_detail(loan_id: int):
    with get_connection() as conn:
        loan = conn.execute(
            """
            SELECT l.*, f.name AS farmer_name
            FROM farmer_loans l
            LEFT JOIN farmers f ON f.id = l.farmer_id
            WHERE l.id = ?
            """,
            (loan_id,),
        ).fetchone()
        repayments = conn.execute(
            """
            SELECT id, repayment_date, amount, method, reference, notes
            FROM loan_repayments
            WHERE loan_id = ?
            ORDER BY date(repayment_date) DESC, id DESC
            """,
            (loan_id,),
        ).fetchall()

    if loan is None:
        flash("Loan not found.", "danger")
        return redirect(url_for("loans.list_loans"))

    principal = float(loan["principal"] or 0)
    repaid = sum(float(r["amount"] or 0) for r in repayments)
    balance = principal - repaid
    return render_template(
        "loans/detail.html",
        loan=loan,
        repayments=repayments,
        summary={"principal": principal, "repaid": repaid, "balance": balance},
    )


@bp.route("/<int:loan_id>/repayments/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "accountant")
def add_repayment(loan_id: int):
    with get_connection() as conn:
        loan = conn.execute("SELECT id, principal, status FROM farmer_loans WHERE id = ?", (loan_id,)).fetchone()
    if loan is None:
        flash("Loan not found.", "danger")
        return redirect(url_for("loans.list_loans"))

    if request.method == "POST":
        repayment_date = (request.form.get("repayment_date") or "").strip() or date.today().isoformat()
        amount_raw = (request.form.get("amount") or "").strip()
        method = (request.form.get("method") or "").strip() or None
        reference = (request.form.get("reference") or "").strip() or None
        notes = (request.form.get("notes") or "").strip() or None

        try:
            amount = float(amount_raw)
        except ValueError:
            flash("Amount must be a number.", "danger")
            return render_template("loans/repayment_form.html", loan_id=loan_id, repayment={"repayment_date": repayment_date})
        if amount <= 0:
            flash("Amount must be greater than 0.", "danger")
            return render_template("loans/repayment_form.html", loan_id=loan_id, repayment={"repayment_date": repayment_date})

        with get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO loan_repayments (loan_id, repayment_date, amount, method, reference, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (loan_id, repayment_date, amount, method, reference, notes),
            )
            repayment_id = cur.lastrowid
            write_audit_log(
                conn,
                user_id=session.get("user_id"),
                action="create",
                entity="loan_repayment",
                entity_id=repayment_id,
                details={"loan_id": loan_id, "amount": amount, "repayment_date": repayment_date},
            )
            conn.commit()

        flash("Repayment recorded.", "success")
        return redirect(url_for("loans.loan_detail", loan_id=loan_id))

    repayment = {"repayment_date": date.today().isoformat()}
    return render_template("loans/repayment_form.html", loan_id=loan_id, repayment=repayment)

