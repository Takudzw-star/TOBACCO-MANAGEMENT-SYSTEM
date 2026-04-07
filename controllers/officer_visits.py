from datetime import date, timedelta

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from controllers.auth import login_required, roles_required
from models.audit import write_audit_log
from models.db import get_connection


bp = Blueprint("officer_visits", __name__, url_prefix="/visits")


def _choices():
    with get_connection() as conn:
        officers = conn.execute("SELECT id, name, region FROM field_officers ORDER BY name ASC").fetchall()
        farmers = conn.execute("SELECT id, name FROM farmers ORDER BY name ASC").fetchall()
        contracts = conn.execute(
            """
            SELECT c.id, f.name AS farmer_name, fo.name AS officer_name
            FROM contracts c
            LEFT JOIN farmers f ON f.id = c.farmer_id
            LEFT JOIN field_officers fo ON fo.id = c.field_officer_id
            ORDER BY c.id DESC
            """
        ).fetchall()
    return officers, farmers, contracts


@bp.get("/")
@login_required
@roles_required("admin", "field_officer")
def list_visits():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
              v.id,
              v.visit_date,
              v.purpose,
              v.notes,
              fo.id AS officer_id,
              fo.name AS officer_name,
              fo.region AS officer_region,
              f.id AS farmer_id,
              f.name AS farmer_name,
              v.contract_id
            FROM officer_visits v
            LEFT JOIN field_officers fo ON fo.id = v.field_officer_id
            LEFT JOIN farmers f ON f.id = v.farmer_id
            ORDER BY v.visit_date DESC, v.id DESC
            """
        ).fetchall()
    return render_template("visits/list.html", visits=rows)


@bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "field_officer")
def create_visit():
    officers, farmers, contracts = _choices()
    if request.method == "POST":
        field_officer_id = request.form.get("field_officer_id")
        farmer_id = request.form.get("farmer_id") or None
        contract_id = request.form.get("contract_id") or None
        visit_date = (request.form.get("visit_date") or "").strip()
        purpose = (request.form.get("purpose") or "").strip() or None
        notes = (request.form.get("notes") or "").strip() or None

        if not field_officer_id or not visit_date:
            flash("Field officer and visit date are required.", "danger")
            return render_template("visits/form.html", row=None, officers=officers, farmers=farmers, contracts=contracts)

        with get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO officer_visits (field_officer_id, farmer_id, contract_id, visit_date, purpose, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    int(field_officer_id),
                    int(farmer_id) if farmer_id else None,
                    int(contract_id) if contract_id else None,
                    visit_date,
                    purpose,
                    notes,
                ),
            )
            visit_id = cur.lastrowid
            write_audit_log(
                conn,
                user_id=session.get("user_id"),
                action="create",
                entity="officer_visit",
                entity_id=visit_id,
                details={"field_officer_id": int(field_officer_id), "visit_date": visit_date},
            )
            conn.commit()

        flash("Visit recorded.", "success")
        return redirect(url_for("officer_visits.list_visits"))

    row = {"visit_date": date.today().isoformat()}
    return render_template("visits/form.html", row=row, officers=officers, farmers=farmers, contracts=contracts)


@bp.route("/<int:visit_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin", "field_officer")
def edit_visit(visit_id: int):
    officers, farmers, contracts = _choices()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, field_officer_id, farmer_id, contract_id, visit_date, purpose, notes
            FROM officer_visits
            WHERE id = ?
            """,
            (visit_id,),
        ).fetchone()

    if row is None:
        flash("Visit not found.", "danger")
        return redirect(url_for("officer_visits.list_visits"))

    if request.method == "POST":
        field_officer_id = request.form.get("field_officer_id")
        farmer_id = request.form.get("farmer_id") or None
        contract_id = request.form.get("contract_id") or None
        visit_date = (request.form.get("visit_date") or "").strip()
        purpose = (request.form.get("purpose") or "").strip() or None
        notes = (request.form.get("notes") or "").strip() or None

        if not field_officer_id or not visit_date:
            flash("Field officer and visit date are required.", "danger")
            return render_template("visits/form.html", row=row, officers=officers, farmers=farmers, contracts=contracts)

        with get_connection() as conn:
            conn.execute(
                """
                UPDATE officer_visits
                SET field_officer_id = ?, farmer_id = ?, contract_id = ?, visit_date = ?, purpose = ?, notes = ?
                WHERE id = ?
                """,
                (
                    int(field_officer_id),
                    int(farmer_id) if farmer_id else None,
                    int(contract_id) if contract_id else None,
                    visit_date,
                    purpose,
                    notes,
                    visit_id,
                ),
            )
            write_audit_log(
                conn,
                user_id=session.get("user_id"),
                action="update",
                entity="officer_visit",
                entity_id=visit_id,
                details={"field_officer_id": int(field_officer_id), "visit_date": visit_date},
            )
            conn.commit()

        flash("Visit updated.", "success")
        return redirect(url_for("officer_visits.list_visits"))

    return render_template("visits/form.html", row=row, officers=officers, farmers=farmers, contracts=contracts)


@bp.post("/<int:visit_id>/delete")
@login_required
@roles_required("admin", "field_officer")
def delete_visit(visit_id: int):
    with get_connection() as conn:
        write_audit_log(
            conn,
            user_id=session.get("user_id"),
            action="delete",
            entity="officer_visit",
            entity_id=visit_id,
            details={},
        )
        conn.execute("DELETE FROM officer_visits WHERE id = ?", (visit_id,))
        conn.commit()

    flash("Visit deleted.", "success")
    return redirect(url_for("officer_visits.list_visits"))


@bp.get("/performance")
@login_required
@roles_required("admin", "field_officer")
def performance():
    today = date.today()
    start_week = today - timedelta(days=today.weekday())
    end_week = start_week + timedelta(days=6)

    with get_connection() as conn:
        leaderboard = conn.execute(
            """
            SELECT
              fo.id AS officer_id,
              fo.name AS officer_name,
              fo.region AS officer_region,
              COUNT(v.id) AS visits_this_week
            FROM field_officers fo
            LEFT JOIN officer_visits v
              ON v.field_officer_id = fo.id
             AND date(v.visit_date) >= date(?)
             AND date(v.visit_date) <= date(?)
            GROUP BY fo.id, fo.name, fo.region
            ORDER BY visits_this_week DESC, fo.name ASC
            """,
            (start_week.isoformat(), end_week.isoformat()),
        ).fetchall()

        engagement = conn.execute(
            """
            SELECT
              fo.id AS officer_id,
              fo.name AS officer_name,
              COUNT(DISTINCT v.farmer_id) AS farmers_engaged_30d
            FROM field_officers fo
            LEFT JOIN officer_visits v
              ON v.field_officer_id = fo.id
             AND v.farmer_id IS NOT NULL
             AND date(v.visit_date) >= date(?, '-30 days')
            GROUP BY fo.id, fo.name
            ORDER BY farmers_engaged_30d DESC
            """,
            (today.isoformat(),),
        ).fetchall()

        # Yield improvements: compare latest season vs previous season per officer
        season_rows = conn.execute(
            "SELECT DISTINCT season FROM yields ORDER BY season DESC"
        ).fetchall()
        latest = season_rows[0]["season"] if season_rows else None
        prev = season_rows[1]["season"] if season_rows and len(season_rows) > 1 else None

        improvements = []
        if latest and prev:
            improvements = conn.execute(
                """
                SELECT
                  fo.id AS officer_id,
                  fo.name AS officer_name,
                  COALESCE(SUM(CASE WHEN y.season = ? THEN y.weight_kg END), 0) AS latest_kg,
                  COALESCE(SUM(CASE WHEN y.season = ? THEN y.weight_kg END), 0) AS prev_kg
                FROM field_officers fo
                LEFT JOIN contracts c ON c.field_officer_id = fo.id
                LEFT JOIN yields y ON y.contract_id = c.id AND (y.season = ? OR y.season = ?)
                GROUP BY fo.id, fo.name
                """,
                (latest, prev, latest, prev),
            ).fetchall()

    return render_template(
        "visits/performance.html",
        week={"start": start_week.isoformat(), "end": end_week.isoformat()},
        leaderboard=leaderboard,
        engagement=engagement,
        improvements=improvements,
        seasons={"latest": latest, "prev": prev},
    )

