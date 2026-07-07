@echo off
REM ── Log Book live self-test (imports + discovery + offline + REAL AI) ────────
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 0
cd /d "%~dp0"
echo Running Log Book self-test... output -> outputs\selftest_report.txt
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" _live_selftest.py
) else (
    python _live_selftest.py
)
echo.
echo ===== SELF-TEST FINISHED =====
pause
