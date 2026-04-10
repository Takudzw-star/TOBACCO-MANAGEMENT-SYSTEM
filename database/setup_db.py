import sqlite3


def _ensure_user_columns(cursor):
    cursor.execute("PRAGMA table_info(users);")
    cols = {row[1] for row in cursor.fetchall()}  # row[1] = name

    if "must_change_password" not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 1;")


def _ensure_contract_columns(cursor):
    cursor.execute("PRAGMA table_info(contracts);")
    cols = {row[1] for row in cursor.fetchall()}
    if "status" not in cols:
        cursor.execute("ALTER TABLE contracts ADD COLUMN status TEXT NOT NULL DEFAULT 'active';")
    if "end_date" not in cols:
        cursor.execute("ALTER TABLE contracts ADD COLUMN end_date DATE;")


def _ensure_contract_tables(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS contract_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS contract_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_id INTEGER NOT NULL,
            template_id INTEGER,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (contract_id) REFERENCES contracts(id),
            FOREIGN KEY (template_id) REFERENCES contract_templates(id)
        );
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS contract_signatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_id INTEGER NOT NULL,
            signer_role TEXT NOT NULL,
            signer_name TEXT NOT NULL,
            signed_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (contract_id) REFERENCES contracts(id)
        );
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS officer_visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_officer_id INTEGER NOT NULL,
            farmer_id INTEGER,
            contract_id INTEGER,
            visit_date DATE NOT NULL,
            purpose TEXT,
            notes TEXT,
            FOREIGN KEY (field_officer_id) REFERENCES field_officers(id),
            FOREIGN KEY (farmer_id) REFERENCES farmers(id),
            FOREIGN KEY (contract_id) REFERENCES contracts(id)
        );
        """
    )


def _ensure_farmer_columns(cursor):
    cursor.execute("PRAGMA table_info(farmers);")
    cols = {row[1] for row in cursor.fetchall()}
    if "land_size_ha" not in cols:
        cursor.execute("ALTER TABLE farmers ADD COLUMN land_size_ha REAL;")
    if "lat" not in cols:
        cursor.execute("ALTER TABLE farmers ADD COLUMN lat REAL;")
    if "lng" not in cols:
        cursor.execute("ALTER TABLE farmers ADD COLUMN lng REAL;")


def _ensure_farmer_crops_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS farmer_crops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id INTEGER NOT NULL,
            season TEXT NOT NULL,
            crop TEXT NOT NULL,
            area_ha REAL,
            notes TEXT,
            FOREIGN KEY (farmer_id) REFERENCES farmers(id)
        );
        """
    )


def _ensure_transaction_columns(cursor):
    cursor.execute("PRAGMA table_info(transactions);")
    cols = {row[1] for row in cursor.fetchall()}
    if "reference" not in cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN reference TEXT;")
    if "tx_type" not in cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN tx_type TEXT NOT NULL DEFAULT 'payment';")


def _ensure_audit_logs_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            entity TEXT NOT NULL,
            entity_id INTEGER,
            details TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
    )


def _ensure_input_catalog(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS input_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            default_unit TEXT,
            default_unit_cost REAL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )

    cursor.execute("PRAGMA table_info(inputs);")
    cols = {row[1] for row in cursor.fetchall()}
    if "item_id" not in cols:
        cursor.execute("ALTER TABLE inputs ADD COLUMN item_id INTEGER;")
    if "unit_cost" not in cols:
        cursor.execute("ALTER TABLE inputs ADD COLUMN unit_cost REAL;")
    if "total_cost" not in cols:
        cursor.execute("ALTER TABLE inputs ADD COLUMN total_cost REAL;")


def _ensure_loan_tables(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS farmer_loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id INTEGER NOT NULL,
            contract_id INTEGER,
            loan_date DATE NOT NULL,
            principal REAL NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            FOREIGN KEY (farmer_id) REFERENCES farmers(id),
            FOREIGN KEY (contract_id) REFERENCES contracts(id)
        );
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS loan_repayments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_id INTEGER NOT NULL,
            repayment_date DATE NOT NULL,
            amount REAL NOT NULL,
            method TEXT,
            reference TEXT,
            notes TEXT,
            FOREIGN KEY (loan_id) REFERENCES farmer_loans(id)
        );
        """
    )


def _ensure_yields_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS yields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_id INTEGER NOT NULL,
            season TEXT NOT NULL,
            grade TEXT,
            weight_kg REAL NOT NULL,
            delivery_date DATE NOT NULL,
            notes TEXT,
            FOREIGN KEY (contract_id) REFERENCES contracts(id)
        );
        """
    )


def _ensure_settings_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )


def _ensure_default_admin(cursor):
    # Create a default admin user if none exist.
    # username: admin
    # password: admin123
    try:
        from werkzeug.security import generate_password_hash
    except Exception:
        # If dependencies aren't installed yet, skip admin creation.
        return

    cursor.execute("SELECT COUNT(*) FROM users;")
    count = cursor.fetchone()[0]
    if count and int(count) > 0:
        return

    cursor.execute(
        """
        INSERT INTO users (username, password_hash, role, is_active, must_change_password)
        VALUES (?, ?, ?, 1, 1)
        """,
        ("admin", generate_password_hash("admin123"), "admin"),
    )


import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.db import DB_PATH

def initialize_database():
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    # Read schema from file using absolute path
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    with open(schema_path, 'r') as schema_file:
        schema = schema_file.read()

    # Execute schema
    cursor.executescript(schema)
    _ensure_user_columns(cursor)
    _ensure_contract_columns(cursor)
    _ensure_contract_tables(cursor)
    _ensure_farmer_columns(cursor)
    _ensure_transaction_columns(cursor)
    _ensure_audit_logs_table(cursor)
    _ensure_input_catalog(cursor)
    _ensure_yields_table(cursor)
    _ensure_farmer_crops_table(cursor)
    _ensure_loan_tables(cursor)
    _ensure_settings_table(cursor)
    _ensure_default_admin(cursor)
    connection.commit()
    connection.close()
    print("Database initialized successfully.")

if __name__ == "__main__":
    initialize_database()