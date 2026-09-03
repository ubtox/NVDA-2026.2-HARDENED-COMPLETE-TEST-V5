@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo NVDA 2026.2 HARDENED V5 - PREPARE + STRICT FULL VALIDATION
echo ============================================================
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0NVDA-HARDENED-PREPARE-SOURCE.ps1"
if errorlevel 1 goto :failed
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0NVDA-HARDENED-VALIDATE.ps1"
if errorlevel 1 goto :failed
echo.
echo ============================================================
echo ALL REQUESTED VALIDATION STEPS PASSED
echo ============================================================
pause
exit /b 0
:failed
echo.
echo ============================================================
echo VALIDATION STOPPED OR FAILED - SEE validation-artifacts
echo If System test preflight failed, use a clean dedicated VM/session.
echo ============================================================
pause
exit /b 1
