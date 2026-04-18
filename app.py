from datetime import date, timedelta

import os

from dotenv import load_dotenv
from flask import Flask, Response, redirect, render_template, request, url_for

from models.db import get_connection

from controllers.auth import bp as auth_bp
from controllers.auth import login_required
from controllers.farmers import bp as farmers_bp
from controllers.field_officers import bp as field_officers_bp
from controllers.contracts import bp as contracts_bp
from controllers.transactions import bp as transactions_bp
from controllers.inputs import bp as inputs_bp
from controllers.input_items import bp as input_items_bp
from controllers.employees import bp as employees_bp
from controllers.reports import bp as reports_bp
from controllers.users import bp as users_bp
from controllers.yields import bp as yields_bp
from controllers.farmer_crops import bp as farmer_crops_bp
from controllers.map_view import bp as map_bp
from controllers.contract_templates import bp as contract_templates_bp
from controllers.contract_documents import bp as contract_documents_bp
from controllers.officer_visits import bp as officer_visits_bp
from controllers.contract_signatures import bp as contract_signatures_bp
from controllers.reminders import bp as reminders_bp
from controllers.analytics import bp as analytics_bp
from controllers.loans import bp as loans_bp
from controllers.finance_dashboard import bp as finance_dashboard_bp
from controllers.search import bp as search_bp
from controllers.offline_drafts import bp as offline_drafts_bp
from controllers.settings import bp as settings_bp, get_setting
from controllers.main_dashboard import bp as main_dashboard_bp


def create_app():
    load_dotenv()
    
    app = Flask(__name__, template_folder="views", static_folder="static")
    secret = os.environ.get("FLASK_SECRET_KEY")
    is_prod = os.environ.get("FLASK_DEBUG", "0") != "1"
    if not secret:
        if is_prod:
            raise RuntimeError("CRITICAL: FLASK_SECRET_KEY must be set in production mode. Refusing to start.")
        secret = "dev_secret_key_change_me"
        print("WARNING: FLASK_SECRET_KEY is not set. Using a development fallback secret.")
    app.secret_key = secret

    from database.setup_db import initialize_database
    initialize_database()
    print("Database checked/initialized inside app.py!")

    app.register_blueprint(auth_bp)
    app.register_blueprint(farmers_bp)
    app.register_blueprint(field_officers_bp)
    app.register_blueprint(contracts_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(inputs_bp)
    app.register_blueprint(input_items_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(yields_bp)
    app.register_blueprint(farmer_crops_bp)
    app.register_blueprint(map_bp)
    app.register_blueprint(contract_templates_bp)
    app.register_blueprint(contract_documents_bp)
    app.register_blueprint(officer_visits_bp)
    app.register_blueprint(contract_signatures_bp)
    app.register_blueprint(reminders_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(loans_bp)
    app.register_blueprint(finance_dashboard_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(offline_drafts_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(main_dashboard_bp)

    _DEFAULT_BANNER = "images/tobacco-field.svg"

    def _resolve_static_image(setting_key: str, default_path: str):
        value = (get_setting(setting_key) or "").strip()
        if not value:
            return default_path

        candidate = os.path.normpath(os.path.join(app.static_folder, value))
        static_root = os.path.normpath(app.static_folder)
        if candidate.startswith(static_root) and os.path.exists(candidate):
            return value
        return default_path

    @app.context_processor
    def inject_branding():
        return {
            "branding": {
                "system_name": get_setting("system_name", "Tobacco Management System"),
                "logo": _resolve_static_image("logo", "images/tobacco-leaf.svg"),
                "dashboard_banner": _resolve_static_image("dashboard_banner", _DEFAULT_BANNER),
                "login_bg": _resolve_static_image("login_bg", _DEFAULT_BANNER),
            }
        }

    @app.get("/")
    def home():
        return render_template("public_home.html")

    @app.get("/robots.txt")
    def robots():
        base = request.url_root.rstrip("/")
        body = "\n".join(
            [
                "User-agent: *",
                "Allow: /",
                "Disallow: /dashboards",
                "Disallow: /auth/change-password",
                "Disallow: /users",
                f"Sitemap: {base}/sitemap.xml",
                "",
            ]
        )
        return Response(body, mimetype="text/plain")

    @app.get("/sitemap.xml")
    def sitemap():
        base = request.url_root.rstrip("/")
        pages = [
            {"loc": f"{base}{url_for('home')}", "priority": "1.0", "changefreq": "weekly"},
        ]
        xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for p in pages:
            xml.extend(
                [
                    "<url>",
                    f"<loc>{p['loc']}</loc>",
                    f"<changefreq>{p['changefreq']}</changefreq>",
                    f"<priority>{p['priority']}</priority>",
                    "</url>",
                ]
            )
        xml.append("</urlset>")
        return Response("\n".join(xml), mimetype="application/xml")

        return Response("\n".join(xml), mimetype="application/xml")

    return app

app = create_app()

@app.after_request
def apply_security_headers(response: Response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    return response


@app.errorhandler(404)
def not_found(_e):
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def internal_error(_e):
    return render_template("errors/500.html"), 500

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug)