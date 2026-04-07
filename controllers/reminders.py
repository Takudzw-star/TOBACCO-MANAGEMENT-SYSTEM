from datetime import date

from flask import Blueprint, render_template, request

from controllers.auth import login_required, roles_required
from models.db import get_connection


bp = Blueprint("reminders", __name__, url_prefix="/reminders")


@bp.get("/")
@login_required
@roles_required("admin", "manager", "field_officer", "accountant")
def reminders_home():
    today = date.today()
    days = request.args.get("days", type=int) or 30
    overdue_days = request.args.get("overdue_days", type=int) or 30

    with get_connection() as conn:
        expiring = conn.execute(
            """
            SELECT c.id, c.end_date, f.name AS farmer_name, fo.name AS officer_name, fo.region AS officer_region
            FROM contracts c
            LEFT JOIN farmers f ON f.id = c.farmer_id
            LEFT JOIN field_officers fo ON fo.id = c.field_officer_id
            WHERE c.status = 'active'
              AND c.end_date IS NOT NULL
              AND date(c.end_date) >= date(?)
              AND date(c.end_date) <= date(?, '+' || ? || ' days')
            ORDER BY date(c.end_date) ASC
            """,
            (today.isoformat(), today.isoformat(), days),
        ).fetchall()

        overdue = conn.execute(
            """
            SELECT
              c.id,
              f.name AS farmer_name,
              fo.name AS officer_name,
              MAX(t.transaction_date) AS last_payment_date,
              COALESCE(SUM(t.amount), 0) AS total_paid
            FROM contracts c
            LEFT JOIN farmers f ON f.id = c.farmer_id
            LEFT JOIN field_officers fo ON fo.id = c.field_officer_id
            LEFT JOIN transactions t ON t.contract_id = c.id
            WHERE c.status = 'active'
            GROUP BY c.id, f.name, fo.name
            HAVING (last_payment_date IS NULL) OR (date(last_payment_date) <= date(?, '-' || ? || ' days'))
            ORDER BY last_payment_date ASC
            """,
            (today.isoformat(), overdue_days),
        ).fetchall()

    return render_template(
        "reminders/index.html",
        filters={"days": days, "overdue_days": overdue_days},
        expiring=expiring,
        overdue=overdue,
    )

