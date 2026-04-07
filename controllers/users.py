from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from controllers.auth import login_required, roles_required
from controllers.auth import validate_password, PASSWORD_RULES
from models.db import get_connection


bp = Blueprint("users", __name__, url_prefix="/users")

ALLOWED_ROLES = ["admin", "manager", "field_officer", "accountant", "hr"]


@bp.get("/")
@login_required
@roles_required("admin")
def list_users():
    with get_connection() as conn:
        users = conn.execute(
            """
            SELECT id, username, role, is_active, created_at
            FROM users
            ORDER BY id DESC
            """
        ).fetchall()
    return render_template("users/list.html", users=users)


@bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_user():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        role = (request.form.get("role") or "").strip()
        password = request.form.get("password") or ""
        is_active = 1 if request.form.get("is_active") == "on" else 0

        if not username or not role or not password:
            flash("Username, role, and password are required.", "danger")
            return render_template("users/form.html", user=None, roles=ALLOWED_ROLES)

        if role not in ALLOWED_ROLES:
            flash("Invalid role.", "danger")
            return render_template("users/form.html", user=None, roles=ALLOWED_ROLES)

        ok, msg = validate_password(password)
        if not ok:
            flash(msg, "danger")
            return render_template(
                "users/form.html", user=None, roles=ALLOWED_ROLES, password_rules=PASSWORD_RULES
            )

        password_hash = generate_password_hash(password)

        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO users (username, password_hash, role, is_active, must_change_password)
                    VALUES (?, ?, ?, ?, 1)
                    """,
                    (username, password_hash, role, is_active),
                )
                conn.commit()
        except Exception:
            flash("Username already exists.", "danger")
            return render_template("users/form.html", user=None, roles=ALLOWED_ROLES)

        flash("User created.", "success")
        return redirect(url_for("users.list_users"))

    return render_template(
        "users/form.html", user=None, roles=ALLOWED_ROLES, password_rules=PASSWORD_RULES
    )


@bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_user(user_id: int):
    with get_connection() as conn:
        user = conn.execute(
            "SELECT id, username, role, is_active, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    if user is None:
        flash("User not found.", "danger")
        return redirect(url_for("users.list_users"))

    if request.method == "POST":
        role = (request.form.get("role") or "").strip()
        is_active = 1 if request.form.get("is_active") == "on" else 0

        if role not in ALLOWED_ROLES:
            flash("Invalid role.", "danger")
            return render_template("users/form.html", user=user, roles=ALLOWED_ROLES)

        # Prevent disabling your own account accidentally
        if session.get("user_id") == user_id:
            is_active = 1

        with get_connection() as conn:
            conn.execute(
                "UPDATE users SET role = ?, is_active = ? WHERE id = ?",
                (role, is_active, user_id),
            )
            conn.commit()

        flash("User updated.", "success")
        return redirect(url_for("users.list_users"))

    return render_template("users/form.html", user=user, roles=ALLOWED_ROLES)


@bp.route("/<int:user_id>/reset-password", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def reset_password(user_id: int):
    with get_connection() as conn:
        user = conn.execute(
            "SELECT id, username, role, is_active FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    if user is None:
        flash("User not found.", "danger")
        return redirect(url_for("users.list_users"))

    if request.method == "POST":
        password = request.form.get("password") or ""
        if not password:
            flash("Password is required.", "danger")
            return render_template("users/reset_password.html", user=user)

        ok, msg = validate_password(password)
        if not ok:
            flash(msg, "danger")
            return render_template(
                "users/reset_password.html", user=user, password_rules=PASSWORD_RULES
            )

        with get_connection() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, must_change_password = 1 WHERE id = ?",
                (generate_password_hash(password), user_id),
            )
            conn.commit()

        flash("Password reset.", "success")
        return redirect(url_for("users.list_users"))

    return render_template("users/reset_password.html", user=user, password_rules=PASSWORD_RULES)

