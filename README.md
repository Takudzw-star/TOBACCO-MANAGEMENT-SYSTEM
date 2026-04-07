# Tobacco Contract Farming Management System

This system is designed to manage tobacco contract farming operations. It includes dashboards for field officers, farmers, accounts, and HR management. The system uses PostgreSQL/MySQL for data storage and is designed to work offline with minimal expenses.

## Tech stack (current)
- **Backend**: Flask (Python)
- **Database**: SQLite (local file `tobacco_management.db`) for offline use
- **UI**: Server-rendered HTML templates in `views/` (Bootstrap via CDN)

## Features
- **Field Officer Dashboard**: Manage farmer contracts and monitor progress.
- **Farmers Dashboard**: View contract details and updates.
- **Accounts Dashboard**: Manage financial transactions and reports.
- **HR Management Dashboard**: Handle employee records and payroll.
- **Database Integration**: PostgreSQL/MySQL for storing all farmer and operational data.
- **Offline Functionality**: Designed to work without internet connectivity.

## Project Structure
- `dashboards/`: Contains dashboard-related code.
- `database/`: Database schema and migration files.
- `models/`: Data models for the application.
- `controllers/`: Business logic and application controllers.
- `views/`: Frontend templates and views.

## Getting Started
1. Create and activate a virtual environment (recommended)

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Initialize (or re-initialize) the database

```bash
python database\setup_db.py
```

4. Run the web app

```bash
python app.py
```

5. Open in your browser
- `http://127.0.0.1:5000/farmers`
- `http://127.0.0.1:5000/field-officers`
- `http://127.0.0.1:5000/dashboards`

## Future Enhancements
- Reporting and analytics.
- Mobile application integration.
- Multi-language support.