from flask import Blueprint, render_template, request

from controllers.auth import login_required
from models.db import get_connection


bp = Blueprint("search", __name__, url_prefix="/search")


@bp.get("/")
@login_required
def search_home():
    q = (request.args.get("q") or "").strip()
    if not q:
        return render_template("search/results.html", q=q, farmers=[], contracts=[], transactions=[])

    like = f"%{q}%"
    with get_connection() as conn:
        farmers = conn.execute(
            """
            SELECT id, name, contact_info
            FROM farmers
            WHERE name LIKE ? OR contact_info LIKE ? OR address LIKE ?
            ORDER BY name ASC
            LIMIT 20
            """,
            (like, like, like),
        ).fetchall()

        contracts = conn.execute(
            """
            SELECT c.id, c.status, f.name AS farmer_name
            FROM contracts c
            LEFT JOIN farmers f ON f.id = c.farmer_id
            WHERE CAST(c.id AS TEXT) LIKE ? OR c.status LIKE ? OR f.name LIKE ?
            ORDER BY c.id DESC
            LIMIT 20
            """,
            (like, like, like),
        ).fetchall()

        transactions = conn.execute(
            """
            SELECT t.id, t.reference, t.tx_type, t.amount, t.transaction_date, t.contract_id
            FROM transactions t
            WHERE t.reference LIKE ? OR t.tx_type LIKE ? OR CAST(t.contract_id AS TEXT) LIKE ?
            ORDER BY t.id DESC
            LIMIT 20
            """,
            (like, like, like),
        ).fetchall()

    return render_template(
        "search/results.html",
        q=q,
        farmers=farmers,
        contracts=contracts,
        transactions=transactions,
    )

