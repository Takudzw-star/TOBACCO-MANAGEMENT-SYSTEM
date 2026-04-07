from datetime import date

from flask import Blueprint, render_template, request

from controllers.auth import login_required, roles_required
from models.db import get_connection


bp = Blueprint("finance_dashboard", __name__, url_prefix="/dashboards/finance")


@bp.get("/")
@login_required
@roles_required("admin", "manager", "accountant")
def finance_home():
    today = date.today()
    overdue_days = request.args.get("overdue_days", type=int) or 30

    with get_connection() as conn:
        totals = conn.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN tx_type = 'payment' THEN amount ELSE 0 END), 0) AS total_paid,
              COALESCE(SUM(CASE WHEN tx_type = 'advance' THEN amount ELSE 0 END), 0) AS total_advances,
              COALESCE(SUM(CASE WHEN tx_type = 'repayment' THEN amount ELSE 0 END), 0) AS total_repayments
            FROM transactions
            """
        ).fetchone()

        pending_payments = conn.execute(
            """
            SELECT COUNT(*) FROM (
              SELECT c.id
              FROM contracts c
              LEFT JOIN transactions t
                ON t.contract_id = c.id AND t.tx_type = 'payment'
              WHERE c.status = 'active'
              GROUP BY c.id
              HAVING COALESCE(SUM(t.amount), 0) = 0
            )
            """
        ).fetchone()[0]

        overdue_payments = conn.execute(
            """
            SELECT COUNT(*) FROM (
              SELECT
                c.id,
                MAX(t.transaction_date) AS last_payment_date
              FROM contracts c
              LEFT JOIN transactions t
                ON t.contract_id = c.id AND t.tx_type = 'payment'
              WHERE c.status = 'active'
              GROUP BY c.id
              HAVING (last_payment_date IS NULL)
                 OR (date(last_payment_date) <= date(?, '-' || ? || ' days'))
            )
            """,
            (today.isoformat(), overdue_days),
        ).fetchone()[0]

        loan_totals = conn.execute(
            """
            SELECT
              COALESCE(SUM(l.principal), 0) AS principal,
              COALESCE(SUM(r.amount), 0) AS repaid
            FROM farmer_loans l
            LEFT JOIN loan_repayments r ON r.loan_id = l.id
            """
        ).fetchone()

        by_farmer = conn.execute(
            """
            SELECT
              f.id AS farmer_id,
              f.name AS farmer_name,
              COALESCE(SUM(CASE WHEN t.tx_type = 'payment' THEN t.amount ELSE 0 END), 0) AS paid,
              COALESCE(SUM(CASE WHEN t.tx_type = 'advance' THEN t.amount ELSE 0 END), 0) AS advances,
              COALESCE(SUM(CASE WHEN t.tx_type = 'repayment' THEN t.amount ELSE 0 END), 0) AS repayments,
              COALESCE(SUM(i.total_cost), 0) AS inputs_cost
            FROM farmers f
            LEFT JOIN contracts c ON c.farmer_id = f.id
            LEFT JOIN transactions t ON t.contract_id = c.id
            LEFT JOIN inputs i ON i.contract_id = c.id
            GROUP BY f.id, f.name
            ORDER BY (repayments - (paid + advances)) DESC, farmer_name ASC
            LIMIT 50
            """
        ).fetchall()

        by_region = conn.execute(
            """
            SELECT
              COALESCE(NULLIF(trim(fo.region), ''), 'Unknown') AS region,
              COALESCE(SUM(CASE WHEN t.tx_type = 'payment' THEN t.amount ELSE 0 END), 0) AS paid,
              COALESCE(SUM(CASE WHEN t.tx_type = 'advance' THEN t.amount ELSE 0 END), 0) AS advances,
              COALESCE(SUM(CASE WHEN t.tx_type = 'repayment' THEN t.amount ELSE 0 END), 0) AS repayments,
              COALESCE(SUM(i.total_cost), 0) AS inputs_cost
            FROM field_officers fo
            LEFT JOIN contracts c ON c.field_officer_id = fo.id
            LEFT JOIN transactions t ON t.contract_id = c.id
            LEFT JOIN inputs i ON i.contract_id = c.id
            GROUP BY region
            ORDER BY (repayments - (paid + advances)) DESC, region ASC
            """
        ).fetchall()

    total_paid = float(totals["total_paid"] or 0)
    total_advances = float(totals["total_advances"] or 0)
    total_repayments = float(totals["total_repayments"] or 0)
    net_cash_position = total_repayments - (total_paid + total_advances)

    loan_principal = float(loan_totals["principal"] or 0)
    loan_repaid = float(loan_totals["repaid"] or 0)
    loan_balance = loan_principal - loan_repaid

    def _row_net(r):
        paid = float(r["paid"] or 0)
        advances = float(r["advances"] or 0)
        repayments = float(r["repayments"] or 0)
        return repayments - (paid + advances)

    farmer_rows = []
    for r in by_farmer:
        farmer_rows.append(
            {
                **dict(r),
                "net": _row_net(r),
            }
        )

    region_rows = []
    for r in by_region:
        region_rows.append(
            {
                **dict(r),
                "net": _row_net(r),
            }
        )

    return render_template(
        "dashboards/finance.html",
        kpis={
            "total_paid": total_paid,
            "total_advances": total_advances,
            "total_repayments": total_repayments,
            "net_cash_position": net_cash_position,
            "pending_payments": int(pending_payments),
            "overdue_payments": int(overdue_payments),
            "overdue_days": int(overdue_days),
            "loan_principal": loan_principal,
            "loan_repaid": loan_repaid,
            "loan_balance": loan_balance,
        },
        by_farmer=farmer_rows,
        by_region=region_rows,
    )

