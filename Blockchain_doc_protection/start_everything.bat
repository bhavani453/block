@echo off
setlocal enabledelayedexpansion
color 0A
echo =========================================================================
echo     BLOCKCHAIN DOCUMENT PROTECTION SYSTEM - COMPLETE STARTUP
echo =========================================================================
echo.

REM ============================================================================
REM STEP 0: CONFIGURATION
REM ============================================================================
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set REQUIRE_IPFS=1

set "PROJECT_ROOT=%~dp0"
set "IPFS_DESKTOP=%LOCALAPPDATA%\Programs\IPFS Desktop\IPFS Desktop.exe"
set "BLOCKCHAIN_PORT=9545"
set "IPFS_PORT=5001"
set "FLASK_PORT=5000"

echo [CONFIG] Project Root: %PROJECT_ROOT%
echo [CONFIG] Blockchain RPC: http://127.0.0.1:%BLOCKCHAIN_PORT%
echo [CONFIG] IPFS API: http://127.0.0.1:%IPFS_PORT%
echo [CONFIG] Flask App: http://127.0.0.1:%FLASK_PORT%
echo.

REM ============================================================================
REM STEP 1: CHECK PREREQUISITES
REM ============================================================================
echo =========================================================================
echo STEP 1: CHECKING PREREQUISITES
echo =========================================================================
echo.

REM Check Python
echo [CHECK] Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Python is not installed or not in PATH
    echo        Install Python 3.8+ from https://python.org
    pause
    exit /b 1
)
for /f "delims=" %%i in ('python --version') do set PYTHON_VER=%%i
echo [OK]    %PYTHON_VER%
echo.

REM Check Node.js
echo [CHECK] Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Node.js is not installed or not in PATH
    echo        Install Node.js 18+ from https://nodejs.org
    pause
    exit /b 1
)
for /f "delims=" %%i in ('node --version') do set NODE_VER=%%i
echo [OK]    Node.js %NODE_VER%
echo.

REM Check Truffle
echo [CHECK] Truffle...
truffle version >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Truffle is not installed
    echo        Install with: npm install -g truffle
    pause
    exit /b 1
)
echo [OK]    Truffle is installed
echo.

REM Check IPFS Desktop
echo [CHECK] IPFS Desktop...
if exist "%IPFS_DESKTOP%" (
    echo [OK]    IPFS Desktop found at: %IPFS_DESKTOP%
) else (
    echo [WARN]  IPFS Desktop not found
    echo        Install with: winget install --id IPFS.IPFS-Desktop -e
    echo        Or download from: https://docs.ipfs.tech/install/ipfs-desktop/
    echo.
    choice /C YN /M "Continue without IPFS"
    if errorlevel 2 exit /b 1
)
echo.

REM Check Python dependencies
echo [CHECK] Python dependencies...
cd /d "%PROJECT_ROOT%Document_Protection_Blockchain"
python -c "import flask, web3, ipfshttpclient, qrcode" >nul 2>&1
if errorlevel 1 (
    echo [WARN]  Some Python dependencies missing
    echo        Installing from requirements.txt...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [FAIL] Failed to install dependencies
        pause
        exit /b 1
    )
)
echo [OK]    All Python dependencies available
echo.

REM ============================================================================
REM STEP 2: STOP ANY EXISTING PROCESSES
REM ============================================================================
echo =========================================================================
echo STEP 2: CLEANING UP EXISTING PROCESSES
echo =========================================================================
echo.

echo [CLEANUP] Checking for existing Flask processes...
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I "python.exe" >NUL
if not errorlevel 1 (
    echo [CLEANUP] Stopping existing Python processes...
    taskkill /F /IM python.exe >nul 2>&1
    timeout /t 2 /nobreak >nul
)
echo [OK]      No conflicting Flask processes
echo.

REM ============================================================================
REM STEP 3: START IPFS
REM ============================================================================
echo =========================================================================
echo STEP 3: STARTING IPFS DAEMON
echo =========================================================================
echo.

if exist "%IPFS_DESKTOP%" (
    echo [IPFS] Checking if IPFS is already running...
    netstat -ano | findstr ":%IPFS_PORT%" | findstr "LISTENING" >nul 2>&1
    if errorlevel 1 (
        echo [IPFS] Starting IPFS Desktop...
        start "" "%IPFS_DESKTOP%"
        echo [IPFS] Waiting for IPFS API to be ready...
        
        set IPFS_RETRY=0
        :WAIT_IPFS
        timeout /t 2 /nobreak >nul
        netstat -ano | findstr ":%IPFS_PORT%" | findstr "LISTENING" >nul 2>&1
        if errorlevel 1 (
            set /a IPFS_RETRY+=1
            if !IPFS_RETRY! LSS 15 (
                echo [IPFS] Waiting... (!IPFS_RETRY!/15^)
                goto WAIT_IPFS
            ) else (
                echo [WARN] IPFS did not start within 30 seconds
                echo        Continuing anyway...
            )
        ) else (
            echo [OK]   IPFS API ready on port %IPFS_PORT%
        )
    ) else (
        echo [OK]   IPFS is already running on port %IPFS_PORT%
    )
) else (
    echo [SKIP] IPFS Desktop not installed
)
echo.

REM ============================================================================
REM STEP 4: START BLOCKCHAIN
REM ============================================================================
echo =========================================================================
echo STEP 4: STARTING BLOCKCHAIN NETWORK
echo =========================================================================
echo.

echo [BLOCKCHAIN] Checking if blockchain is already running...
netstat -ano | findstr ":%BLOCKCHAIN_PORT%" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [BLOCKCHAIN] Starting Truffle Develop blockchain...
    cd /d "%PROJECT_ROOT%hello-eth"
    
    REM Start blockchain in new window
    start "Blockchain RPC Server" cmd /c "truffle develop"
    
    echo [BLOCKCHAIN] Waiting for RPC server to be ready...
    set BC_RETRY=0
    :WAIT_BLOCKCHAIN
    timeout /t 2 /nobreak >nul
    netstat -ano | findstr ":%BLOCKCHAIN_PORT%" | findstr "LISTENING" >nul 2>&1
    if errorlevel 1 (
        set /a BC_RETRY+=1
        if !BC_RETRY! LSS 10 (
            echo [BLOCKCHAIN] Waiting... (!BC_RETRY!/10^)
            goto WAIT_BLOCKCHAIN
        ) else (
            echo [FAIL] Blockchain did not start within 20 seconds
            echo        Please check the Blockchain window for errors
            pause
            exit /b 1
        )
    ) else (
        echo [OK]   Blockchain RPC ready on port %BLOCKCHAIN_PORT%
    )
) else (
    echo [OK]   Blockchain is already running on port %BLOCKCHAIN_PORT%
)
echo.

REM ============================================================================
REM STEP 5: START FLASK APPLICATION
REM ============================================================================
echo =========================================================================
echo STEP 5: STARTING FLASK APPLICATION
echo =========================================================================
echo.

cd /d "%PROJECT_ROOT%Document_Protection_Blockchain"

echo [FLASK] Starting Flask web application...
start "Flask Web Server" cmd /c "python MainEnhanced.py"

echo [FLASK] Waiting for Flask to be ready...
set FLASK_RETRY=0
:WAIT_FLASK
timeout /t 2 /nobreak >nul
netstat -ano | findstr ":%FLASK_PORT%" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    set /a FLASK_RETRY+=1
    if !FLASK_RETRY! LSS 10 (
        echo [FLASK] Waiting... (!FLASK_RETRY!/10^)
        goto WAIT_FLASK
    ) else (
        echo [FAIL] Flask did not start within 20 seconds
        echo        Please check the Flask window for errors
        pause
        exit /b 1
    )
) else (
    echo [OK]   Flask ready on port %FLASK_PORT%
)
echo.

REM ============================================================================
REM STEP 6: VERIFY ALL SERVICES
REM ============================================================================
echo =========================================================================
echo STEP 6: VERIFYING ALL SERVICES
echo =========================================================================
echo.

set ALL_OK=1

REM Verify IPFS
if exist "%IPFS_DESKTOP%" (
    netstat -ano | findstr ":%IPFS_PORT%" | findstr "LISTENING" >nul 2>&1
    if errorlevel 1 (
        echo [FAIL] IPFS API is NOT accessible on port %IPFS_PORT%
        set ALL_OK=0
    ) else (
        echo [OK]   IPFS API is accessible on port %IPFS_PORT%
    )
)

REM Verify Blockchain
netstat -ano | findstr ":%BLOCKCHAIN_PORT%" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Blockchain RPC is NOT accessible on port %BLOCKCHAIN_PORT%
    set ALL_OK=0
) else (
    echo [OK]   Blockchain RPC is accessible on port %BLOCKCHAIN_PORT%
)

REM Verify Flask
netstat -ano | findstr ":%FLASK_PORT%" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Flask is NOT accessible on port %FLASK_PORT%
    set ALL_OK=0
) else (
    echo [OK]   Flask is accessible on port %FLASK_PORT%
)

echo.

REM ============================================================================
REM STEP 7: SUMMARY
REM ============================================================================
echo =========================================================================
echo                    STARTUP COMPLETE
echo =========================================================================
echo.

if %ALL_OK%==1 (
    echo [SUCCESS] All services are running!
    echo.
    echo ┌─────────────────────────────────────────────────────────────────┐
    echo │                       ACCESS INFORMATION                        │
    echo ├─────────────────────────────────────────────────────────────────┤
    echo │                                                                 │
    echo │  🌐 Web Application:  http://127.0.0.1:%FLASK_PORT%                     │
    echo │  ⛓️  Blockchain RPC:   http://127.0.0.1:%BLOCKCHAIN_PORT%                     │
    if exist "%IPFS_DESKTOP%" (
        echo │  📦 IPFS API:         http://127.0.0.1:%IPFS_PORT%                     │
    )
    echo │                                                                 │
    echo ├─────────────────────────────────────────────────────────────────┤
    echo │                      DEMO CREDENTIALS                           │
    echo ├─────────────────────────────────────────────────────────────────┤
    echo │                                                                 │
    echo │  Admin:         admin        / admin123                        │
    echo │  Investigator:  investigator / investigator123                 │
    echo │  Demo User:     demo         / demo123                         │
    echo │  Viewer:        viewer       / viewer123                       │
    echo │                                                                 │
    echo └─────────────────────────────────────────────────────────────────┘
    echo.
    echo [INFO] Opening web browser...
    timeout /t 2 /nobreak >nul
    start http://127.0.0.1:%FLASK_PORT%
) else (
    echo [WARNING] Some services failed to start properly
    echo           Please check the service windows for error messages
)

echo.
echo [INFO] Press any key to keep services running and close this window...
echo        Or close all service windows to stop the application.
pause >nul

endlocal
