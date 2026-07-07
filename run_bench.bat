@echo off
REM ── IGP + Log Book benchmark (real Gemini). Arg: igp | logbook | both ────────
powercfg /change standby-timeout-ac 0 >nul 2>&1
powercfg /change monitor-timeout-ac 0 >nul 2>&1
cd /d "%~dp0"
set "ARGS=%*"
if "%ARGS%"=="" set "ARGS=both"
echo Running benchmark (%ARGS%)... output -> outputs\bench_report.txt
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" _bench.py %ARGS%
) else (
    python _bench.py %ARGS%
)
echo ===== BENCH DONE =====
