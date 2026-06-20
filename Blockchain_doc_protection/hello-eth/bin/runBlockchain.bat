@echo off
echo ===========================================
echo  Blockchain Document Protection System
echo  Starting Ethereum Development Network
echo ===========================================
echo.

REM Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Node.js is not installed or not in PATH
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

REM Check if Truffle is installed
truffle version >nul 2>&1
if errorlevel 1 (
    echo ❌ Truffle is not installed
    echo Installing Truffle globally...
    npm install -g truffle
    if errorlevel 1 (
        echo ❌ Failed to install Truffle
        pause
        exit /b 1
    )
)

echo ✅ Node.js and Truffle are ready
echo.

REM Navigate to the hello-eth directory
cd /d "%~dp0.."

echo 📁 Current directory: %CD%
echo.

REM Clean any previous builds
echo 🧹 Cleaning previous builds...
if exist build\ (
    rmdir /s /q build
)

REM Install dependencies if package.json exists
if exist package.json (
    echo 📦 Installing dependencies...
    npm install
    echo.
)

REM Compile smart contracts
echo 🔨 Compiling smart contracts...
truffle compile
if errorlevel 1 (
    echo ❌ Contract compilation failed
    pause
    exit /b 1
)
echo ✅ Contracts compiled successfully
echo.

REM Start the development blockchain
echo 🚀 Starting Ethereum development network...
echo.
echo ===========================================
echo  Blockchain Network Information:
echo ===========================================
echo 📡 RPC Server: http://127.0.0.1:9545
echo 🔗 Network ID: 1337
echo 👤 Accounts: 10 pre-funded accounts available
echo 💰 ETH per account: 100 ETH
echo.
echo 📋 Available Accounts:
echo 0: 0x19Caf90a78aAD07868e04229F817264056472EE6
echo 1: 0x4a4c2b3c1d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9
echo 2: 0x5b5c3d4e6f7a8b9c0d1e2f3a4b5c6d7e8f0a1
echo ===========================================
echo.

truffle develop

echo.
echo ===========================================
echo  Blockchain network stopped
echo ===========================================
pause