-- Database schema for Tobacco Contract Farming Management System (SQLite)

-- NOTE:
-- Use IF NOT EXISTS so setup_db.py can be re-run safely.

-- Users (authentication & roles)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Table for storing farmer information
CREATE TABLE IF NOT EXISTS farmers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact_info TEXT,
    address TEXT,
    contract_status BOOLEAN DEFAULT 0,
    land_size_ha REAL,
    lat REAL,
    lng REAL
);

-- Crop history per farmer (optional, used for intelligence)
CREATE TABLE IF NOT EXISTS farmer_crops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER NOT NULL,
    season TEXT NOT NULL,
    crop TEXT NOT NULL,
    area_ha REAL,
    notes TEXT,
    FOREIGN KEY (farmer_id) REFERENCES farmers(id)
);

-- Table for storing field officer information
CREATE TABLE IF NOT EXISTS field_officers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    region TEXT,
    contact_info TEXT
);

-- Table for storing contracts
CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER,
    field_officer_id INTEGER,
    status TEXT NOT NULL DEFAULT 'draft',
    contract_date DATE,
    end_date DATE,
    details TEXT,
    FOREIGN KEY (farmer_id) REFERENCES farmers(id),
    FOREIGN KEY (field_officer_id) REFERENCES field_officers(id)
);

-- Contract templates and generated documents (automation)
CREATE TABLE IF NOT EXISTS contract_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

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

-- Digital signatures (simple typed name for now)
CREATE TABLE IF NOT EXISTS contract_signatures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER NOT NULL,
    signer_role TEXT NOT NULL,
    signer_name TEXT NOT NULL,
    signed_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (contract_id) REFERENCES contracts(id)
);

-- Field officer visits (performance tracking)
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

-- Table for storing HR data
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    position TEXT,
    salary REAL,
    hire_date DATE
);

-- Table for storing financial transactions
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER,
    reference TEXT,
    tx_type TEXT NOT NULL DEFAULT 'payment',
    amount REAL,
    transaction_date DATE,
    description TEXT,
    FOREIGN KEY (contract_id) REFERENCES contracts(id)
);

-- Audit log (who did what, when)
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

-- Inputs / inventory issued to a contract
CREATE TABLE IF NOT EXISTS inputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER NOT NULL,
    item_id INTEGER,
    item TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit TEXT,
    unit_cost REAL,
    total_cost REAL,
    issue_date DATE,
    description TEXT,
    FOREIGN KEY (contract_id) REFERENCES contracts(id),
    FOREIGN KEY (item_id) REFERENCES input_items(id)
);

-- Input catalog / supply chain
CREATE TABLE IF NOT EXISTS input_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    default_unit TEXT,
    default_unit_cost REAL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Loans / advances and repayments (financial intelligence)
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

-- Yield / harvest deliveries (production)
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

-- System settings (branding, config)
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);