from datetime import date, timedelta
from flask import Blueprint, request, render_template
from models.db import get_connection
from controllers.auth import login_required

bp = Blueprint("main_dashboard", __name__)

@bp.get("/dashboards")
@login_required
def dashboards():
    # Metrics are global for now (no user->field officer mapping yet)
    today = date.today()
    overdue_days = 30
    expiring_days = 330
    default_season = f"{today.year}/{today.year + 1}"
    selected_season = request.args.get("season") or ""

    with get_connection() as conn:
        season_rows = conn.execute(
            """
            SELECT DISTINCT season
            FROM yields
            WHERE season IS NOT NULL AND trim(season) <> ''
            ORDER BY season DESC
            """
        ).fetchall()
        available_seasons = [r["season"] for r in season_rows]
        if not selected_season:
            selected_season = available_seasons[0] if available_seasons else default_season

        total_farmers = conn.execute("SELECT COUNT(*) FROM farmers;").fetchone()[0]
        active_contracts = conn.execute(
            "SELECT COUNT(*) FROM contracts WHERE status = 'active';"
        ).fetchone()[0]

        pending_payments = conn.execute(
            """
            SELECT COUNT(*) FROM (
              SELECT c.id
              FROM contracts c
              LEFT JOIN transactions t ON t.contract_id = c.id AND t.tx_type = 'payment'
              WHERE c.status = 'active'
              GROUP BY c.id
              HAVING COALESCE(SUM(t.amount), 0) = 0
            )
            """
        ).fetchone()[0]

        revenue_total = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE tx_type = 'payment';"
        ).fetchone()[0]

        yield_this_season = conn.execute(
            """
            SELECT COALESCE(SUM(weight_kg), 0)
            FROM yields
            WHERE season = ?
            """,
            (selected_season,),
        ).fetchone()[0]

        # Production trend: total yield by month (last 12 months)
        start_12m = today.replace(day=1) - timedelta(days=365)
        trend_rows = conn.execute(
            """
            SELECT substr(delivery_date, 1, 7) AS ym, COALESCE(SUM(weight_kg), 0) AS total
            FROM yields
            WHERE delivery_date IS NOT NULL AND delivery_date >= ?
            GROUP BY ym
            ORDER BY ym ASC
            """,
            (start_12m.isoformat(),),
        ).fetchall()

        trend = [{"ym": r["ym"], "total": float(r["total"] or 0)} for r in trend_rows]

        grade_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(trim(grade), ''), 'Unknown') AS grade, COALESCE(SUM(weight_kg), 0) AS total
            FROM yields
            WHERE season = ?
            GROUP BY grade
            ORDER BY total DESC
            """,
            (selected_season,),
        ).fetchall()
        grade_summary = [{"grade": r["grade"], "total": float(r["total"] or 0)} for r in grade_rows]

        region_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(trim(region), ''), 'Unknown') AS region, COUNT(*) AS cnt
            FROM field_officers
            GROUP BY region
            ORDER BY cnt DESC
            """
        ).fetchall()
        region_distribution = [{"region": r["region"], "count": int(r["cnt"])} for r in region_rows]

        expiring_contracts = conn.execute(
            """
            SELECT c.id, c.end_date, f.name AS farmer_name
            FROM contracts c
            LEFT JOIN farmers f ON f.id = c.farmer_id
            WHERE c.status = 'active'
              AND c.end_date IS NOT NULL
              AND date(c.end_date) >= date(?)
              AND date(c.end_date) <= date(?, '+' || ? || ' days')
            ORDER BY date(c.end_date) ASC
            LIMIT 10
            """,
            (today.isoformat(), today.isoformat(), expiring_days),
        ).fetchall()

        overdue_contracts = conn.execute(
            """
            SELECT
              c.id,
              f.name AS farmer_name,
              MAX(t.transaction_date) AS last_payment_date,
              COALESCE(SUM(t.amount), 0) AS total_paid
            FROM contracts c
            LEFT JOIN farmers f ON f.id = c.farmer_id
            LEFT JOIN transactions t ON t.contract_id = c.id AND t.tx_type = 'payment'
            WHERE c.status = 'active'
            GROUP BY c.id, f.name
            HAVING (last_payment_date IS NULL) OR (date(last_payment_date) <= date(?, '-' || ? || ' days'))
            ORDER BY last_payment_date ASC
            LIMIT 10
            """,
            (today.isoformat(), overdue_days),
        ).fetchall()

        status_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(trim(status), ''), 'Unknown') AS status, COUNT(*) AS cnt
            FROM contracts
            GROUP BY status
            ORDER BY cnt DESC
            """
        ).fetchall()
        contract_status = [{"status": r["status"], "count": int(r["cnt"])} for r in status_rows]

        activity_rows = conn.execute(
            """
            SELECT
              a.created_at,
              a.action,
              a.entity,
              a.entity_id,
              u.username AS username
            FROM audit_logs a
            LEFT JOIN users u ON u.id = a.user_id
            ORDER BY a.id DESC
            LIMIT 10
            """
        ).fetchall()

        low_activity_regions = conn.execute(
            """
            SELECT
              COALESCE(NULLIF(trim(fo.region), ''), 'Unknown') AS region,
              COALESCE(SUM(t.amount), 0) AS total_amount
            FROM field_officers fo
            LEFT JOIN contracts c ON c.field_officer_id = fo.id
            LEFT JOIN transactions t ON t.contract_id = c.id
              AND t.transaction_date IS NOT NULL
              AND date(t.transaction_date) >= date(?, '-90 days')
            GROUP BY region
            ORDER BY total_amount ASC
            LIMIT 5
            """,
            (today.isoformat(),),
        ).fetchall()

    return render_template(
        "dashboards.html",
        metrics={
            "total_farmers": int(total_farmers),
            "active_contracts": int(active_contracts),
            "revenue_total": float(revenue_total or 0),
            "pending_payments": int(pending_payments),
            "yield_this_season": float(yield_this_season or 0),
            "season": selected_season,
        },
        charts={
            "trend": trend,
            "region_distribution": region_distribution,
            "grade_summary": grade_summary,
            "contract_status": contract_status,
        },
        filters={"available_seasons": available_seasons},
        alerts={
            "expiring_contracts": expiring_contracts,
            "overdue_contracts": overdue_contracts,
            "low_activity_regions": low_activity_regions,
            "overdue_days": overdue_days,
            "expiring_days": expiring_days,
        },
        activity=activity_rows,
    )
