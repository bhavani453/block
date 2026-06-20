@echo off
echo ============================================
echo  Blockchain Document Protection System
echo ============================================
echo.

echo Checking prerequisites...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

echo ✅ Python found
python --version
echo.

REM Check if Node.js is installed
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js is not installed or not in PATH
    echo Please install Node.js 14+ from https://nodejs.org
    pause
    exit /b 1
)

echo ✅ Node.js found
node --version
echo.

echo Installing Python dependencies...
cd Document_Protection_Blockchain
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo ❌ Failed to install Python dependencies
    pause
    exit /b 1
)

echo ✅ Python dependencies installed
echo.

echo ============================================
echo  Installation Complete!
echo ============================================
echo.
echo Next steps:
echo 1. Start the blockchain: Run start_blockchain.bat
echo 2. Start the web app: Run 'python MainEnhanced.py' in Document_Protection_Blockchain folder
echo 3. Open browser to: http://127.0.0.1:5000
echo.
echo Demo credentials:
echo - Admin: admin / admin123
echo - User: demo / demo123
echo.

pause