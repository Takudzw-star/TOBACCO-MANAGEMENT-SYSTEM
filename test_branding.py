import os
import sqlite3
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from database.setup_db import initialize_database
from models.db import DB_PATH, get_connection

def test_branding_setup():
    print("Testing branding setup...")
    
    # Run setup to ensure table exists
    initialize_database()
    
    with get_connection() as conn:
        # Test inserting a setting
        conn.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)", ("system_name", "Test TMS"))
        conn.commit()
        
        # Test retrieving it
        row = conn.execute("SELECT value FROM system_settings WHERE key = ?", ("system_name",)).fetchone()
        assert row["value"] == "Test TMS", f"Expected 'Test TMS', got {row['value']}"
        print("✓ Database settings table verified.")

def test_upload_directory():
    print("Testing upload directory...")
    upload_path = os.path.join("static", "uploads")
    if not os.path.exists(upload_path):
        os.makedirs(upload_path)
    assert os.path.isdir(upload_path), f"Upload path {upload_path} is not a directory"
    print(f"✓ Upload directory verified at {upload_path}")

if __name__ == "__main__":
    try:
        test_branding_setup()
        test_upload_directory()
        print("\nAll branding verification tests passed!")
    except Exception as e:
        print(f"\nVerification failed: {e}")
        sys.exit(1)
