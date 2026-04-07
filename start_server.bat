@echo off
echo ==================================================
echo Tobacco Management System Production Server
echo ==================================================

echo Installing/Verifying dependencies...
pip install -r requirements.txt

echo.
echo Starting Waitress server...
python run_waitress.py

pause
