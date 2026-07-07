@echo off
REM ── India Glycols Document Intelligence — local host launcher ────────────────
REM Keeps the machine awake (on AC), starts the Streamlit server on port 8501 in
REM its own window, then opens the browser to the app.

REM Prevent the device from sleeping / screen turning off while plugged in.
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 0
powercfg /change hibernate-timeout-ac 0

cd /d "%~dp0"
set "PORT=8501"
echo Starting India Glycols Document Intelligence on http://localhost:%PORT% ...

REM Stop any previous server instance so the newest code is loaded (safe no-op
REM if none is running).
taskkill /F /FI "WINDOWTITLE eq IGL Document Intelligence (server)*" >nul 2>&1

REM Launch the server in its own window (non-blocking).
if exist ".venv\Scripts\python.exe" (
    start "IGL Document Intelligence (server)" ".venv\Scripts\python.exe" -m streamlit run app.py --server.headless true --server.port %PORT% --server.address 0.0.0.0
) else (
    start "IGL Document Intelligence (server)" python -m streamlit run app.py --server.headless true --server.port %PORT% --server.address 0.0.0.0
)

REM Give the server a few seconds, then open the app in the default browser.
echo Waiting for the server to come up...
timeout /t 10 /nobreak >nul
start "" "http://localhost:%PORT%"

echo.
echo App is running at http://localhost:%PORT%  (keep the server window open).
timeout /t 4 /nobreak >nul
