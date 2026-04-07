from datetime import date

import csv
from io import StringIO

from flask import Blueprint, Response, render_template, request

from controllers.auth import login_required, roles_required
from models.db import get_connection


bp = Blueprint("reports", __name__, url_prefix="/reports")


def _date_range_from_request():
    start_date = request.args.get("start_date") or ""
    end_date = request.args.get("end_date") or ""

    if not start_date:
        today = date.today()
        start_date = today.replace(day=1).isoformat()
    if not end_date:
        end_date = date.today().isoformat()

    return start_date, end_date


def _fetch_reports(start_date: str, end_date: str):
    with get_connection() as conn:
        overall = conn.execute(
            """
            SELECT
              COUNT(*) AS tx_count,
              COALESCE(SUM(amount), 0) AS total_amount
            FROM transactions
            WHERE transaction_date IS NOT NULL
              AND transaction_date >= ?
              AND transaction_date <= ?
            """,
            (start_date, end_date),
        ).fetchone()

        by_farmer = conn.execute(
            """
            SELECT
              f.id AS farmer_id,
              f.name AS farmer_name,
              COUNT(t.id) AS tx_count,
              COALESCE(SUM(t.amount), 0) AS total_amount
            FROM transactions t
            JOIN contracts c ON c.id = t.contract_id
            JOIN farmers f ON f.id = c.farmer_id
            WHERE t.transaction_date IS NOT NULL
              AND t.transaction_date >= ?
              AND t.transaction_date <= ?
            GROUP BY f.id, f.name
            ORDER BY total_amount DESC
            """,
            (start_date, end_date),
        ).fetchall()

        by_officer = conn.execute(
            """
            SELECT
              fo.id AS field_officer_id,
              fo.name AS field_officer_name,
              fo.region AS field_officer_region,
              COUNT(t.id) AS tx_count,
              COALESCE(SUM(t.amount), 0) AS total_amount
            FROM transactions t
            JOIN contracts c ON c.id = t.contract_id
            JOIN field_officers fo ON fo.id = c.field_officer_id
            WHERE t.transaction_date IS NOT NULL
              AND t.transaction_date >= ?
              AND t.transaction_date <= ?
            GROUP BY fo.id, fo.name, fo.region
            ORDER BY total_amount DESC
            """,
            (start_date, end_date),
        ).fetchall()

    return overall, by_farmer, by_officer


@bp.get("/")
@login_required
@roles_required("admin", "accountant", "manager")
def reports_home():
    start_date, end_date = _date_range_from_request()
    overall, by_farmer, by_officer = _fetch_reports(start_date, end_date)

    return render_template(
        "reports/index.html",
        start_date=start_date,
        end_date=end_date,
        overall=overall,
        by_farmer=by_farmer,
        by_officer=by_officer,
    )


@bp.get("/export.csv")
@login_required
@roles_required("admin", "accountant", "manager")
def export_reports_csv():
    start_date, end_date = _date_range_from_request()
    overall, by_farmer, by_officer = _fetch_reports(start_date, end_date)

    buf = StringIO()
    w = csv.writer(buf)

    w.writerow(["Report", "Transactions", "Total Amount", "Start Date", "End Date"])
    w.writerow(["Overall", overall["tx_count"], overall["total_amount"], start_date, end_date])
    w.writerow([])

    w.writerow(["Totals by farmer"])
    w.writerow(["Farmer ID", "Farmer Name", "Transactions", "Total Amount", "Start Date", "End Date"])
    for r in by_farmer:
        w.writerow([r["farmer_id"], r["farmer_name"], r["tx_count"], r["total_amount"], start_date, end_date])
    w.writerow([])

    w.writerow(["Totals by field officer"])
    w.writerow(
        ["Field Officer ID", "Field Officer Name", "Region", "Transactions", "Total Amount", "Start Date", "End Date"]
    )
    for r in by_officer:
        w.writerow(
            [
                r["field_officer_id"],
                r["field_officer_name"],
                r["field_officer_region"],
                r["tx_count"],
                r["total_amount"],
                start_date,
                end_date,
            ]
        )

    filename = f"tms-reports_{start_date}_to_{end_date}.csv"
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

