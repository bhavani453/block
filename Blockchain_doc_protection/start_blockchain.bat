@echo off
echo Starting Blockchain Document Protection System...
echo.

REM Navigate to hello-eth directory and run blockchain
cd /d "%~dp0hello-eth\bin"
call runBlockchain.bat

pause