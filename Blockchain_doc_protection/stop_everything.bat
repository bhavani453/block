@echo off
setlocal enabledelayedexpansion
color 0C
echo =========================================================================
echo     BLOCKCHAIN DOCUMENT PROTECTION - STOP ALL SERVICES
echo =========================================================================
echo.

echo [STOPPING] Shutting down all services...
echo.

REM ============================================================================
REM Stop Flask (Python)
REM ============================================================================
echo [1/3] Stopping Flask Application...
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I "python.exe" >NUL
if not errorlevel 1 (
    echo       Terminating Python processes...
    taskkill /F /IM python.exe >nul 2>&1
    if errorlevel 1 (
        echo       [WARN] Could not stop some Python processes
    ) else (
        echo       [OK]   Flask stopped
    )
) else (
    echo       [INFO] Flask was not running
)
echo.

REM ============================================================================
REM Stop Blockchain (Node/Truffle)
REM ============================================================================
echo [2/3] Stopping Blockchain Network...
tasklist /FI "IMAGENAME eq node.exe" 2>NUL | find /I "node.exe" >NUL
if not errorlevel 1 (
    echo       Terminating Node.js/Truffle processes...
    taskkill /F /IM node.exe >nul 2>&1
    if errorlevel 1 (
        echo       [WARN] Could not stop some Node processes
    ) else (
        echo       [OK]   Blockchain stopped
    )
) else (
    echo       [INFO] Blockchain was not running
)
echo.

REM ============================================================================
REM Stop IPFS Desktop (optional - user might want to keep it running)
REM ============================================================================
echo [3/3] IPFS Desktop Status...
tasklist /FI "IMAGENAME eq IPFS Desktop.exe" 2>NUL | find /I "IPFS Desktop.exe" >NUL
if not errorlevel 1 (
    echo       IPFS Desktop is running
    echo.
    choice /C YN /M "       Stop IPFS Desktop? (You might want to keep it running)"
    if not errorlevel 2 (
        echo       Stopping IPFS Desktop...
        taskkill /F /IM "IPFS Desktop.exe" >nul 2>&1
        if errorlevel 1 (
            echo       [WARN] Could not stop IPFS Desktop
        ) else (
            echo       [OK]   IPFS Desktop stopped
        )
    ) else (
        echo       [INFO] Keeping IPFS Desktop running
    )
) else (
    echo       [INFO] IPFS Desktop was not running
)
echo.

REM ============================================================================
REM Verify all stopped
REM ============================================================================
echo =========================================================================
echo Verifying services stopped...
echo =========================================================================
echo.

set "BLOCKCHAIN_PORT=9545"
set "IPFS_PORT=5001"
set "FLASK_PORT=5000"

set ALL_STOPPED=1

REM Check Flask
netstat -ano | findstr ":%FLASK_PORT%" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [WARN] Flask is still running on port %FLASK_PORT%
    set ALL_STOPPED=0
) else (
    echo [OK]   Flask stopped (port %FLASK_PORT% is free)
)

REM Check Blockchain
netstat -ano | findstr ":%BLOCKCHAIN_PORT%" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [WARN] Blockchain is still running on port %BLOCKCHAIN_PORT%
    set ALL_STOPPED=0
) else (
    echo [OK]   Blockchain stopped (port %BLOCKCHAIN_PORT% is free)
)

echo.

if %ALL_STOPPED%==1 (
    echo =========================================================================
    echo [SUCCESS] All services stopped successfully!
    echo =========================================================================
) else (
    echo =========================================================================
    echo [WARNING] Some services are still running
    echo           You may need to close their windows manually
    echo =========================================================================
)

echo.
echo Press any key to exit...
pause >nul
endlocal
