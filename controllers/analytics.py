from flask import Blueprint, render_template, request

from controllers.auth import login_required, roles_required
from models.db import get_connection


bp = Blueprint("analytics", __name__, url_prefix="/analytics")


@bp.get("/inputs-vs-yield")
@login_required
@roles_required("admin", "manager", "accountant", "field_officer")
def inputs_vs_yield():
    season = (request.args.get("season") or "").strip() or None

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
        if season is None and available_seasons:
            season = available_seasons[0]

        rows = conn.execute(
            """
            SELECT
              c.id AS contract_id,
              COALESCE(f.name, '—') AS farmer_name,
              COALESCE(fo.region, 'Unknown') AS region,
              COALESCE(SUM(i.total_cost), 0) AS inputs_cost,
              COALESCE(SUM(y.weight_kg), 0) AS yield_kg
            FROM contracts c
            LEFT JOIN farmers f ON f.id = c.farmer_id
            LEFT JOIN field_officers fo ON fo.id = c.field_officer_id
            LEFT JOIN inputs i ON i.contract_id = c.id
            LEFT JOIN yields y ON y.contract_id = c.id
              AND (? IS NULL OR y.season = ?)
            WHERE c.status IN ('active', 'completed')
            GROUP BY c.id, f.name, fo.region
            ORDER BY yield_kg DESC, inputs_cost DESC
            LIMIT 200
            """,
            (season, season),
        ).fetchall()

        data = []
        for r in rows:
            inputs_cost = float(r["inputs_cost"] or 0)
            yield_kg = float(r["yield_kg"] or 0)
            cost_per_kg = (inputs_cost / yield_kg) if yield_kg > 0 else None
            data.append(
                {
                    "contract_id": int(r["contract_id"]),
                    "farmer_name": r["farmer_name"],
                    "region": r["region"] or "Unknown",
                    "inputs_cost": inputs_cost,
                    "yield_kg": yield_kg,
                    "cost_per_kg": cost_per_kg,
                }
            )

        region_rows = conn.execute(
            """
            SELECT
              COALESCE(NULLIF(trim(fo.region), ''), 'Unknown') AS region,
              COALESCE(SUM(i.total_cost), 0) AS inputs_cost,
              COALESCE(SUM(y.weight_kg), 0) AS yield_kg
            FROM contracts c
            LEFT JOIN field_officers fo ON fo.id = c.field_officer_id
            LEFT JOIN inputs i ON i.contract_id = c.id
            LEFT JOIN yields y ON y.contract_id = c.id
              AND (? IS NULL OR y.season = ?)
            WHERE c.status IN ('active', 'completed')
            GROUP BY region
            ORDER BY yield_kg DESC
            """,
            (season, season),
        ).fetchall()

        regions = []
        for r in region_rows:
            inputs_cost = float(r["inputs_cost"] or 0)
            yield_kg = float(r["yield_kg"] or 0)
            regions.append(
                {
                    "region": r["region"],
                    "inputs_cost": inputs_cost,
                    "yield_kg": yield_kg,
                    "cost_per_kg": (inputs_cost / yield_kg) if yield_kg > 0 else None,
                }
            )

    return render_template(
        "analytics/inputs_vs_yield.html",
        season=season,
        available_seasons=available_seasons,
        rows=data,
        regions=regions,
    )

