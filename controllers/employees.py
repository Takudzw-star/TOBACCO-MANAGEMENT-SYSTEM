from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from controllers.auth import login_required, roles_required
from models.db import get_connection


bp = Blueprint("employees", __name__, url_prefix="/employees")


@bp.get("/")
@login_required
@roles_required("admin", "hr")
def list_employees():
    with get_connection() as conn:
        employees = conn.execute(
            "SELECT id, name, position, salary, hire_date FROM employees ORDER BY id DESC"
        ).fetchall()
    return render_template("employees/list.html", employees=employees)


@bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "hr")
def create_employee():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        position = (request.form.get("position") or "").strip() or None
        salary_raw = (request.form.get("salary") or "").strip()
        hire_date = (request.form.get("hire_date") or "").strip() or None

        if not name:
            flash("Name is required.", "danger")
            return render_template("employees/form.html", employee=None)

        salary = None
        if salary_raw:
            try:
                salary = float(salary_raw)
            except ValueError:
                flash("Salary must be a number.", "danger")
                return render_template("employees/form.html", employee=None)

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO employees (name, position, salary, hire_date) VALUES (?, ?, ?, ?)",
                (name, position, salary, hire_date),
            )
            conn.commit()

        flash("Employee created.", "success")
        return redirect(url_for("employees.list_employees"))

    employee = {"hire_date": date.today().isoformat()}
    return render_template("employees/form.html", employee=employee)


@bp.route("/<int:employee_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin", "hr")
def edit_employee(employee_id: int):
    with get_connection() as conn:
        employee = conn.execute(
            "SELECT id, name, position, salary, hire_date FROM employees WHERE id = ?",
            (employee_id,),
        ).fetchone()

    if employee is None:
        flash("Employee not found.", "danger")
        return redirect(url_for("employees.list_employees"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        position = (request.form.get("position") or "").strip() or None
        salary_raw = (request.form.get("salary") or "").strip()
        hire_date = (request.form.get("hire_date") or "").strip() or None

        if not name:
            flash("Name is required.", "danger")
            return render_template("employees/form.html", employee=employee)

        salary = None
        if salary_raw:
            try:
                salary = float(salary_raw)
            except ValueError:
                flash("Salary must be a number.", "danger")
                return render_template("employees/form.html", employee=employee)

        with get_connection() as conn:
            conn.execute(
                """
                UPDATE employees
                SET name = ?, position = ?, salary = ?, hire_date = ?
                WHERE id = ?
                """,
                (name, position, salary, hire_date, employee_id),
            )
            conn.commit()

        flash("Employee updated.", "success")
        return redirect(url_for("employees.list_employees"))

    return render_template("employees/form.html", employee=employee)


@bp.post("/<int:employee_id>/delete")
@login_required
@roles_required("admin", "hr")
def delete_employee(employee_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
        conn.commit()

    flash("Employee deleted.", "success")
    return redirect(url_for("employees.list_employees"))

