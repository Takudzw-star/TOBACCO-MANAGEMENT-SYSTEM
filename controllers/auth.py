from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from models.db import get_connection


bp = Blueprint("auth", __name__, url_prefix="/auth")

PASSWORD_RULES = "At least 8 characters, with at least 1 letter and 1 number."

ROLE_ALIASES = {
    # Legacy -> canonical
    "accounts": "accountant",
    # Canonical
    "accountant": "accountant",
    "admin": "admin",
    "manager": "manager",
    "field_officer": "field_officer",
    "hr": "hr",
}


def normalize_role(role: str | None) -> str | None:
    if role is None:
        return None
    role = (role or "").strip()
    return ROLE_ALIASES.get(role, role)


def role_in(role: str | None, allowed_roles: tuple[str, ...]) -> bool:
    r = normalize_role(role)
    allowed = {normalize_role(x) for x in allowed_roles}
    return r in allowed


def validate_password(pw: str):
    if pw is None:
        return False, PASSWORD_RULES
    pw = pw.strip()
    if len(pw) < 8:
        return False, PASSWORD_RULES
    has_letter = any(ch.isalpha() for ch in pw)
    has_digit = any(ch.isdigit() for ch in pw)
    if not (has_letter and has_digit):
        return False, PASSWORD_RULES
    return True, ""


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login", next=request.full_path))
        return view(*args, **kwargs)

    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("auth.login", next=request.full_path))
            role = session.get("role")
            if not role_in(role, roles):
                flash("You do not have permission to access this page.", "danger")
                return redirect(url_for("dashboards"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


@bp.route("/login", methods=["GET", "POST"])
def login():
    next_url = request.args.get("next") or url_for("dashboards")
    if request.method == "POST":
        user_id_raw = (request.form.get("user_id") or "").strip()
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        next_url = request.form.get("next_url") or next_url

        with get_connection() as conn:
            if user_id_raw:
                try:
                    user_id = int(user_id_raw)
                except ValueError:
                    user_id = None
                if user_id is not None:
                    user = conn.execute(
                        """
                        SELECT id, username, password_hash, role, is_active, must_change_password
                        FROM users
                        WHERE id = ?
                        """,
                        (user_id,),
                    ).fetchone()
                else:
                    user = None
            else:
                user = conn.execute(
                    """
                    SELECT id, username, password_hash, role, is_active, must_change_password
                    FROM users
                    WHERE username = ?
                    """,
                    (username,),
                ).fetchone()

        if user is None or not user["is_active"]:
            flash("Invalid username or password.", "danger")
            return render_template("auth/login.html", next_url=next_url)

        if not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.", "danger")
            return render_template("auth/login.html", next_url=next_url)

        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = normalize_role(user["role"])
        if user["must_change_password"]:
            session["post_change_next"] = next_url
            flash("Please change your password to continue.", "warning")
            return redirect(url_for("auth.change_password"))

        flash("Welcome!", "success")
        return redirect(next_url)

    with get_connection() as conn:
        users = conn.execute(
            """
            SELECT id, username, role
            FROM users
            WHERE is_active = 1
            ORDER BY role ASC, username ASC
            """
        ).fetchall()

    user_choices = [{"id": u["id"], "username": u["username"], "role": normalize_role(u["role"])} for u in users]

    return render_template(
        "auth/login.html",
        next_url=next_url,
        password_rules=PASSWORD_RULES,
        user_choices=user_choices,
    )


@bp.get("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password") or ""
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not new_password:
            flash("New password is required.", "danger")
            return render_template("auth/change_password.html")

        if new_password != confirm_password:
            flash("New password and confirmation do not match.", "danger")
            return render_template("auth/change_password.html")

        ok, msg = validate_password(new_password)
        if not ok:
            flash(msg, "danger")
            return render_template("auth/change_password.html", password_rules=PASSWORD_RULES)

        user_id = session.get("user_id")
        with get_connection() as conn:
            user = conn.execute(
                "SELECT id, password_hash FROM users WHERE id = ? AND is_active = 1",
                (user_id,),
            ).fetchone()

            if user is None or not check_password_hash(user["password_hash"], current_password):
                flash("Current password is incorrect.", "danger")
                return render_template("auth/change_password.html")

            conn.execute(
                "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
                (generate_password_hash(new_password), user_id),
            )
            conn.commit()

        flash("Password changed.", "success")
        next_url = session.pop("post_change_next", None) or url_for("dashboards")
        return redirect(next_url)

    return render_template("auth/change_password.html", password_rules=PASSWORD_RULES)

