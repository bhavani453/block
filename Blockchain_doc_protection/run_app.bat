@echo off
echo ============================================
echo  Starting Blockchain Document Protection
echo ============================================
echo.

REM Ensure Python uses UTF-8 output (avoids UnicodeEncodeError on Windows)
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

REM Require IPFS when starting via this script
set REQUIRE_IPFS=1

cd Document_Protection_Blockchain

echo Starting Flask web application...
echo Access at: http://127.0.0.1:5000
echo Press Ctrl+C to stop
echo.

python MainEnhanced.py

pause