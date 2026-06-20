@echo off
echo ===========================================
echo  Blockchain Document Protection System
echo  Quick Start Script
echo ===========================================
echo.

REM Ensure Python uses UTF-8 output (avoids UnicodeEncodeError on Windows)
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

REM Require IPFS when starting via quick start
set REQUIRE_IPFS=1

echo Step 0: Checking and Starting IPFS...
set "IPFS_DESKTOP=%LOCALAPPDATA%\Programs\IPFS Desktop\IPFS Desktop.exe"
if exist "%IPFS_DESKTOP%" (
	echo ✅ IPFS Desktop found
	start "IPFS Desktop" "%IPFS_DESKTOP%"
	echo ✅ IPFS Desktop launched
) else (
	echo ⚠️  IPFS Desktop not found. Attempting to download and install...
	echo.
	echo Checking for winget...
	where winget >nul 2>&1
	if %ERRORLEVEL% EQU 0 (
		echo ✅ Winget found. Installing IPFS Desktop...
		winget install --id IPFS.IPFS-Desktop -e --silent --accept-package-agreements --accept-source-agreements
		if %ERRORLEVEL% EQU 0 (
			echo ✅ IPFS Desktop installed successfully
			timeout /t 2 /nobreak >nul
			if exist "%IPFS_DESKTOP%" (
				start "IPFS Desktop" "%IPFS_DESKTOP%"
				echo ✅ IPFS Desktop launched
			) else (
				echo ⚠️  Installation completed but IPFS Desktop not found in expected location
				echo Please restart this script or install manually
			)
		) else (
			echo ❌ Failed to install IPFS Desktop
			echo Please install manually from: https://docs.ipfs.tech/install/ipfs-desktop/
		)
	) else (
		echo ❌ Winget not found. Cannot auto-install IPFS Desktop
		echo.
		echo Please install IPFS Desktop manually:
		echo 1. Visit: https://docs.ipfs.tech/install/ipfs-desktop/
		echo 2. Download and install IPFS Desktop
		echo 3. Run this script again
		echo.
		echo Or install winget and run this script again
		pause
		exit /b 1
	)
)

timeout /t 5 /nobreak >nul

echo Step 1: Starting Blockchain Network...
echo.
cd /d "%~dp0hello-eth\bin"
start cmd /k "runBlockchain.bat"

timeout /t 5 /nobreak >nul

echo.
echo Step 2: Starting Flask Application...
echo.
cd /d "%~dp0Document_Protection_Blockchain"
start cmd /k "python MainEnhanced.py"

echo.
echo ===========================================
echo  System Status:
echo ===========================================
echo ✅ Blockchain Network: http://127.0.0.1:9545
echo ✅ Flask Application: http://127.0.0.1:5000
echo.
echo 📱 Access the application at: http://127.0.0.1:5000
echo.
echo 🔑 Demo Credentials:
echo    Admin: admin / admin123
echo    User:  investigator / investigator123
echo ===========================================
echo.
echo Press any key to exit...
pause >nul