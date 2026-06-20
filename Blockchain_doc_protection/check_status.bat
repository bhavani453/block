@echo off
setlocal enabledelayedexpansion
color 0B
echo =========================================================================
echo     BLOCKCHAIN DOCUMENT PROTECTION - STATUS CHECK
echo =========================================================================
echo.

set "BLOCKCHAIN_PORT=9545"
set "IPFS_PORT=5001"
set "FLASK_PORT=5000"
set "IPFS_DESKTOP=%LOCALAPPDATA%\Programs\IPFS Desktop\IPFS Desktop.exe"

echo Checking all services...
echo.

REM ============================================================================
REM Check IPFS
REM ============================================================================
echo [CHECKING] IPFS Daemon (Port %IPFS_PORT%)
echo --------------------------------------------------------------------
if exist "%IPFS_DESKTOP%" (
    netstat -ano | findstr ":%IPFS_PORT%" | findstr "LISTENING" >nul 2>&1
    if errorlevel 1 (
        echo [STATUS]   NOT RUNNING
        echo [ACTION]   Start IPFS Desktop or run: start_everything.bat
    ) else (
        echo [STATUS]   RUNNING
        echo [URL]      http://127.0.0.1:%IPFS_PORT%
        
        REM Try to get IPFS version
        for /f "delims=" %%i in ('powershell -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:5001/api/v0/version' -UseBasicParsing -TimeoutSec 2).Content | ConvertFrom-Json | Select-Object -ExpandProperty Version } catch { 'N/A' }"') do set IPFS_VER=%%i
        if not "!IPFS_VER!"=="" if not "!IPFS_VER!"=="N/A" (
            echo [VERSION]   !IPFS_VER!
        )
    )
) else (
    echo [STATUS]   IPFS Desktop not installed
    echo [ACTION]   Install with: winget install --id IPFS.IPFS-Desktop -e
)
echo.

REM ============================================================================
REM Check Blockchain
REM ============================================================================
echo [CHECKING] Blockchain RPC (Port %BLOCKCHAIN_PORT%)
echo --------------------------------------------------------------------
netstat -ano | findstr ":%BLOCKCHAIN_PORT%" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [STATUS]   NOT RUNNING
    echo [ACTION]   Run: truffle develop (in hello-eth folder)
) else (
    echo [STATUS]   RUNNING
    echo [URL]      http://127.0.0.1:%BLOCKCHAIN_PORT%
    
    REM Get process details
    for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%BLOCKCHAIN_PORT%" ^| findstr "LISTENING"') do (
        echo [PID]      %%p
        for /f "tokens=1" %%n in ('tasklist /FI "PID eq %%p" /NH 2^>nul') do echo [PROCESS]  %%n
    )
    
    REM Try to get chain ID
    powershell -Command "$result = try { $body = '{\"jsonrpc\":\"2.0\",\"method\":\"eth_chainId\",\"params\":[],\"id\":1}'; $response = Invoke-WebRequest -Uri 'http://127.0.0.1:9545' -Method POST -Body $body -ContentType 'application/json' -UseBasicParsing -TimeoutSec 2; $json = $response.Content | ConvertFrom-Json; [Convert]::ToInt32($json.result, 16) } catch { 'N/A' }; Write-Output $result" > temp_chain.txt
    set /p CHAIN_ID=<temp_chain.txt
    del temp_chain.txt >nul 2>&1
    if not "!CHAIN_ID!"=="" if not "!CHAIN_ID!"=="N/A" (
        echo [CHAIN ID] !CHAIN_ID!
    )
)
echo.

REM ============================================================================
REM Check Flask
REM ============================================================================
echo [CHECKING] Flask Application (Port %FLASK_PORT%)
echo --------------------------------------------------------------------
netstat -ano | findstr ":%FLASK_PORT%" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [STATUS]   NOT RUNNING
    echo [ACTION]   Run: python MainEnhanced.py (in Document_Protection_Blockchain folder)
) else (
    echo [STATUS]   RUNNING
    echo [URL]      http://127.0.0.1:%FLASK_PORT%
    
    REM Get process details
    for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%FLASK_PORT%" ^| findstr "LISTENING"') do (
        echo [PID]      %%p
        for /f "tokens=1" %%n in ('tasklist /FI "PID eq %%p" /NH 2^>nul') do echo [PROCESS]  %%n
    )
    
    REM Try to access the test endpoint
    powershell -Command "$result = try { (Invoke-WebRequest -Uri 'http://127.0.0.1:5000/test' -UseBasicParsing -TimeoutSec 2).StatusCode } catch { 'ERROR' }; Write-Output $result" > temp_http.txt
    set /p HTTP_STATUS=<temp_http.txt
    del temp_http.txt >nul 2>&1
    if "!HTTP_STATUS!"=="200" (
        echo [HTTP]     Responding (Status 200 OK)
    ) else (
        echo [HTTP]     Not responding or error
    )
)
echo.

REM ============================================================================
REM Summary
REM ============================================================================
echo =========================================================================
echo                            SUMMARY
echo =========================================================================
echo.

set SERVICE_COUNT=0
set RUNNING_COUNT=0

REM Count services
if exist "%IPFS_DESKTOP%" (
    set /a SERVICE_COUNT+=1
    netstat -ano | findstr ":%IPFS_PORT%" | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 set /a RUNNING_COUNT+=1
)

set /a SERVICE_COUNT+=2
netstat -ano | findstr ":%BLOCKCHAIN_PORT%" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 set /a RUNNING_COUNT+=1

netstat -ano | findstr ":%FLASK_PORT%" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 set /a RUNNING_COUNT+=1

echo Services Running: !RUNNING_COUNT! / !SERVICE_COUNT!
echo.

if !RUNNING_COUNT!==!SERVICE_COUNT! (
    echo [SUCCESS] ✅ All services are operational!
    echo.
    echo           Open your browser to: http://127.0.0.1:%FLASK_PORT%
    echo.
    echo           Demo Credentials:
    echo           - Admin:        admin / admin123
    echo           - Investigator: investigator / investigator123
    echo.
) else (
    echo [WARNING] ⚠️  Some services are not running
    echo.
    echo           To start all services, run: start_everything.bat
    echo.
)

echo =========================================================================
echo.
pause
endlocal
