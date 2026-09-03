@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo NVDA 2026.2 HARDENED V5 - INTERACTIVE DETERMINISTIC BUILD
echo SYSTEM TESTS WILL BE SKIPPED
echo ============================================================
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0NVDA-HARDENED-PREPARE-SOURCE.ps1"
if errorlevel 1 goto :failed
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0NVDA-HARDENED-VALIDATE.ps1" -SkipSystemTests
if errorlevel 1 goto :failed
echo.
echo ============================================================
echo DETERMINISTIC CHECKS + PACKAGING PASSED
echo ROBOT SYSTEM TESTS WERE NOT EXECUTED
echo ============================================================
pause
exit /b 0
:failed
echo.
echo ============================================================
echo VALIDATION OR BUILD FAILED - SEE validation-artifacts
echo ============================================================
pause
exit /b 1
