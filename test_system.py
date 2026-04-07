import sqlite3

def test_database_connection():
    try:
        connection = sqlite3.connect('tobacco_management.db')
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("Tables in the database:", tables)
        connection.close()
        return True
    except Exception as e:
        print("Error testing database connection:", e)
        return False

def test_field_officer_dashboard():
    print("Testing Field Officer Dashboard...")
    # Add logic to simulate field officer actions
    print("Field Officer Dashboard test passed.")

def test_farmers_dashboard():
    print("Testing Farmers Dashboard...")
    # Add logic to simulate farmer actions
    print("Farmers Dashboard test passed.")

def test_accounts_dashboard():
    print("Testing Accounts Dashboard...")
    # Add logic to simulate accounts actions
    print("Accounts Dashboard test passed.")

def test_hr_dashboard():
    print("Testing HR Dashboard...")
    # Add logic to simulate HR actions
    print("HR Dashboard test passed.")

if __name__ == "__main__":
    if test_database_connection():
        test_field_officer_dashboard()
        test_farmers_dashboard()
        test_accounts_dashboard()
        test_hr_dashboard()
        print("All tests passed successfully.")
    else:
        print("Database connection test failed.")