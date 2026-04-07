import os
from dotenv import load_dotenv
from waitress import serve
from app import app

load_dotenv()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting Waitress production server on port {port}...")
    serve(app, host='0.0.0.0', port=port)
